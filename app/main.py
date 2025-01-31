from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
from typing import Dict, List

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .models.project import ProjectCreate

load_dotenv()


from .db.init import close_db, init_db
from .git.exceptions import RepositoryValidationError
from .git.manager import GitManager
from .models.project import ProjectCreate
from .db.project import create_project, get_all_projects

logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent.parent
OLLAMA_BASE_URL = "http://localhost:11434"
ACTIVE_MODEL = "qwen2.5-coder:7b-instruct-q8_0"


@asynccontextmanager
async def lifespan(app:FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")



templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


async def get_ollama_models() -> List[Dict]:
    """
    Fetches available models from Ollama's API. This function makes an HTTP request
    to Ollama's local API endpoint and processes the response to get model information.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                # Sort models by name for better presentation
                return sorted(models, key=lambda x: x["name"])
            return []
        except Exception as e:
            print(f"Error fetching models: {e}")
            return []


@app.get("/")
async def root(request: Request):
    """
    Renders the main page. We fetch available models and pass them to the template
    so users can see and select from installed models immediately upon loading.
    """
    models = await get_ollama_models()
    projects= await get_all_projects()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "models": models, "active_model": ACTIVE_MODEL, "projects": projects},
    )


@app.post("/set-model")
async def set_model(request: Request):
    """
    Updates the active model based on user selection. Returns a response that
    HTMX will use to update the UI, confirming the model change.
    """
    try:
        form = await request.form()
        model_name = form.get("model")
        if model_name:
            global ACTIVE_MODEL
            ACTIVE_MODEL = model_name
            return templates.TemplateResponse(
                "partials/model_status.html",
                {"request": request, "active_model": ACTIVE_MODEL},
            )
    except Exception as e:
        return HTMLResponse(f"Error setting model: {str(e)}", status_code=500)


@app.post("/chat")
async def chat(request: Request):
    """
    Handles chat messages by sending them to Ollama and processing the streamed response.
    The function now properly handles Ollama's streaming response format.
    """
    try:
        # Get the message from form data
        form = await request.form()
        message = form.get("message", "")

        if not message or message.isspace():
            return templates.TemplateResponse(
                "partials/error.html",
                {"request": request, "error": "Please enter a message"},
                status_code=400,
            )

        # Initialize response accumulator
        full_response = ""

        # Make request to Ollama
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": ACTIVE_MODEL,
                    "prompt": message,
                    "stream": True,  # Enable streaming
                },
            ) as response:
                # Process the streaming response
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        # Parse each line as a separate JSON object
                        chunk = json.loads(line)

                        # Extract the response text from the chunk
                        if "response" in chunk:
                            full_response += chunk["response"]

                        # Check if this is the final message
                        if chunk.get("done", False):
                            break

                    except json.JSONDecodeError as e:
                        print(f"Error parsing chunk: {line}")
                        print(f"Error details: {str(e)}")
                        continue

        # Return the complete response
        return templates.TemplateResponse(
            "partials/message.html",
            {
                "request": request,
                "message": full_response.strip(),
                "model": ACTIVE_MODEL,
            },
        )

    except Exception as e:
        print(f"Error processing chat: {str(e)}")
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": f"Failed to process message: {str(e)}"},
            status_code=500,
        )


@app.get("/select-project")
async def select_project(request: Request):
    """
    Handle the project selection dialog display.
    Returns the project selection dialog HTML template.
    """
    try:
        # We'll extend this later to include recently used projects
        # or default paths based on configuration
        return templates.TemplateResponse(
            "partials/project_dialog.html",
            {
                "request": request,
            },
        )
    except Exception as e:
        print(f"Error displaying project selection: {e}")
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "Failed to load project selection dialog"},
            status_code=500,
        )


git_manager = GitManager("./workspace")


@app.post("/analyze-project")
async def analyze_project(request: Request):
    try:
        form = await request.form()
        repo_path = form.get("repo_path")
        
        if not repo_path:
            return templates.TemplateResponse(
                "partials/error.html",
                {"request": request, "error": "Repository path or URL is required"},
                status_code=400,
            )

        # Initialize repository - now persistent
        repo_info = await git_manager.initialize_repository(repo_path)
        
        # Create project in database with git-specific info
        project_data = ProjectCreate(
            name=repo_info.name,
            repo_url=repo_path,
            repo_path=str(repo_info.path),  # Store the actual path where git data lives
            default_branch=repo_info.default_branch,
            current_branch=repo_info.default_branch,
            last_commit=repo_info.last_commit,
            description=None,
        )
        project_id = await create_project(project_data)
        
        # Get initial file tree using Git's internal structure
        files = await git_manager.get_file_tree()
        
        # Get additional git metadata
        file_history_sample = []
        try:
            # Get history of first 3 files as a sample
            for file in files[:3]:
                history = await git_manager.get_file_history(file['path'])
                file_history_sample.append({
                    'path': file['path'],
                    'commits': len(history),
                    'last_modified': history[0]['date'] if history else None
                })
        except Exception as e:
            logger.warning(f"Could not fetch file history: {e}")
        
        return templates.TemplateResponse(
            "partials/project_status.html",
            {
                "request": request,
                "repo_path": str(repo_info.path),
                "status": "initialized",
                "message": f"Repository initialized successfully: {repo_info.name}",
                "details": {
                    "name": repo_info.name,
                    "id": project_id,
                    "default_branch": repo_info.default_branch,
                    "current_commit": repo_info.last_commit,
                    "commit_count": repo_info.commit_count,
                    "branch_count": repo_info.branch_count,
                    "file_count": len(files),
                    "file_samples": file_history_sample
                },
            },
        )
    except RepositoryValidationError as e:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": str(e)},
            status_code=400,
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return templates.TemplateResponse(
            "partials/error.html",
            {
                "request": request,
                "error": "An unexpected error occurred while analyzing the repository",
            },
            status_code=500,
        )
