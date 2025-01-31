from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path

app = FastAPI()

# Set up templates and static files
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

@app.post("/chat")
async def chat(request: Request, message: str = Form(...)):
    """
    Handle chat messages coming from the form.
    The Form(...) dependency tells FastAPI to expect form-encoded data.
    """
    return templates.TemplateResponse(
        "partials/message.html",
        {
            "request": request,
            "message": message
        }
    )

# Optional: Add error handling for a better user experience
@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """
    Handle any unexpected errors and return a nice error message to the user
    """
    return templates.TemplateResponse(
        "partials/error.html",
        {
            "request": request,
            "error": str(exc)
        },
        status_code=500
    )
