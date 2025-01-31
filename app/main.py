from dotenv import load_dotenv


from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
from pathlib import Path
from typing import List, Dict
import json

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from typing import Optional
import logging


load_dotenv()


from .git.manager import GitManager
from .git.exceptions import RepositoryValidationError
from .db.main import init_db, close_db




BASE_DIR = Path(__file__).resolve().parent.parent
OLLAMA_BASE_URL = "http://localhost:11434"
ACTIVE_MODEL = "qwen2.5-coder:7b-instruct-q8_0"



app = FastAPI()
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")



@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    await close_db()



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
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "models": models,
            "active_model": ACTIVE_MODEL
        }
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
                {
                    "request": request,
                    "active_model": ACTIVE_MODEL
                }
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
                {
                    "request": request,
                    "error": "Please enter a message"
                },
                status_code=400
            )

        # Initialize response accumulator
        full_response = ""
        
        # Make request to Ollama
        async with httpx.AsyncClient() as client:
            async with client.stream('POST', f"{OLLAMA_BASE_URL}/api/generate", 
                json={
                    "model": ACTIVE_MODEL,
                    "prompt": message,
                    "stream": True  # Enable streaming
                }
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
                "model": ACTIVE_MODEL
            }
        )

    except Exception as e:
        print(f"Error processing chat: {str(e)}")
        return templates.TemplateResponse(
            "partials/error.html",
            {
                "request": request,
                "error": f"Failed to process message: {str(e)}"
            },
            status_code=500
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
            }
        )
    except Exception as e:
        print(f"Error displaying project selection: {e}")
        return templates.TemplateResponse(
            "partials/error.html",
            {
                "request": request,
                "error": "Failed to load project selection dialog"
            },
            status_code=500
        )

# Initialize GitManager with a workspace directory
git_manager = GitManager("./workspace")

@app.post("/analyze-project")
async def analyze_project(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle repository initialization and analysis.
    Supports both local paths and remote Git URLs.
    """
    try:
        form = await request.form()
        repo_source = form.get("repo_path")
        
        if not repo_source:
            return templates.TemplateResponse(
                "partials/error.html",
                {
                    "request": request,
                    "error": "Repository path or URL is required"
                },
                status_code=400
            )

        # Initialize repository
        repo_info = await git_manager.initialize_repository(repo_source)
       
        print(repo_info)
        # Get initial file tree
        files = await git_mananager.get_file_tree()
        
        # Add cleanup to background tasks for remote repositories
        if not repo_info.is_local:
            background_tasks.add_task(git_manager.cleanup)

        return templates.TemplateResponse(
            "partials/project_status.html",
            {
                "request": request,
                "repo_path": str(repo_info.path),
                "status": "initialized",
                "message": f"Repository initialized successfully: {repo_info.name}",
                "details": {
                    "name": repo_info.name,
                    "default_branch": repo_info.default_branch,
                    "commit_count": repo_info.commit_count,
                    "branch_count": repo_info.branch_count,
                    "file_count": len(files)
                }
            }
        )

    except RepositoryValidationError as e:
        logger.error(f"Repository validation error: {str(e)}")
        return templates.TemplateResponse(
            "partials/error.html",
            {
                "request": request,
                "error": str(e)
            },
            status_code=400
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return templates.TemplateResponse(
            "partials/error.html",
            {
                "request": request,
                "error": "An unexpected error occurred while analyzing the repository"
            },
            status_code=500
        )
