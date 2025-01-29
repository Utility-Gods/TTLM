from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult
from io import BytesIO
from typing import Dict
from fastapi import HTTPException
import json

class PDFService:
    def __init__(self):
        self.doc_converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
        )
    
    def generate_catalogue(self, data: Dict) -> BytesIO:
        try:
            # Convert data to docling format
            docling_content = self._prepare_docling_content(data)
            
            # Create document using docling
            doc = self.doc_converter.create_document(docling_content)
            
            # Convert to PDF
            pdf_buffer = BytesIO()
            doc.export_to_pdf(pdf_buffer)
            pdf_buffer.seek(0)
            
            return pdf_buffer
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    def _prepare_docling_content(self, data: Dict) -> dict:
        content = {
            "title": data.get("title", "Product Catalogue"),
            "sections": []
        }
        
        for product in data.get("products", []):
            section = {
                "heading": product["name"],
                "content": [],
                "images": []
            }
            
            # Add details
            for key, value in product.get("details", {}).items():
                section["content"].append(f"{key}: {value}")
            
            # Add images
            for img in product.get("images", []):
                section["images"].append({
                    "url": img["url"],
                    "caption": img.get("caption", "")
                })
                
            content["sections"].append(section)
            
        return content
