from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import pdf

app = FastAPI(title="Photoship API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(pdf.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
