from typing import Dict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..services.pdf_service import PDFService

router = APIRouter(prefix="/pdf", tags=["pdf"])
pdf_service = PDFService()


@router.post("/generate")
async def generate_pdf(data: Dict):
    pdf_buffer = pdf_service.generate_catalogue(data)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=catalogue_{data.get('id')}.pdf"
        },
    )
