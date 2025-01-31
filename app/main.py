# app/main.py
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
from pathlib import Path
from typing import List, Dict
import json

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# We'll store the active model name in memory for this simple implementation
# In a production app, you might want to use a proper state management solution
OLLAMA_BASE_URL = "http://localhost:11434"
ACTIVE_MODEL = "qwen2.5-coder:7b-instruct-q8_0"



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
