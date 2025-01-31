# app/main.py
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
import json
from pathlib import Path
from typing import AsyncGenerator

app = FastAPI()

# Setup for templates and static files
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Configuration for Ollama with Qwen2.5 Coder
OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "qwen2.5-coder:7b-instruct-q8_0"

async def generate_code_response(message: str) -> AsyncGenerator[str, None]:
    """
    Generates responses using Qwen2.5 Coder model. The function is structured to:
    1. Format the prompt to get the best results from the model
    2. Stream the response back in chunks
    3. Handle any errors gracefully
    """
    async with httpx.AsyncClient(timeout=30.0) as client:  # Increased timeout for longer responses
        try:
            # Format the prompt to get more focused coding responses
            formatted_prompt = f"""Please help with the following coding question or task. 
            Provide clear, well-commented code and explain your solution.

            Question/Task: {message}

            Response:"""

            url = f"{OLLAMA_BASE_URL}/api/generate"
            data = {
                "model": MODEL_NAME,
                "prompt": formatted_prompt,
                "stream": True,
                # Optional parameters you might want to tune:
                # "temperature": 0.7,
                # "top_p": 0.9,
                # "top_k": 40,
            }

            async with client.stream('POST', url, json=data) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            if 'response' in chunk:
                                yield chunk['response']
                            # Check if we're done generating
                            if chunk.get('done', False):
                                break
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPError as exc:
            yield f"Error communicating with the model: {str(exc)}"
        except Exception as exc:
            yield f"Unexpected error: {str(exc)}"

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

@app.post("/chat")
async def chat(
    request: Request,
    message: str = Form(...)
):
    """
    Handles chat messages by sending them to the Qwen2.5 Coder model and returning the response.
    This function:
    1. Validates the input
    2. Sends it to the model
    3. Collects and formats the response
    4. Handles any markdown or code formatting in the response
    """
    try:
        if not message.strip():
            return templates.TemplateResponse(
                "partials/error.html",
                {
                    "request": request,
                    "error": "Please enter a message"
                },
                status_code=400
            )

        # Collect the full response
        response_text = ""
        async for chunk in generate_code_response(message):
            response_text += chunk

        # Clean up the response and format it
        response_text = response_text.strip()
        
        # Return the response
        return templates.TemplateResponse(
            "partials/message.html",
            {
                "request": request,
                "message": response_text,
                "is_code_response": True  # This flag helps our template handle code formatting
            }
        )

    except Exception as e:
        return templates.TemplateResponse(
            "partials/error.html",
            {
                "request": request,
                "error": f"Failed to get response: {str(e)}"
            },
            status_code=500
        )

# Error Handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return templates.TemplateResponse(
        "partials/error.html",
        {
            "request": request,
            "error": str(exc)
        },
        status_code=500
    )
