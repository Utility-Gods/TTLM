from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    repo_url: str

class ProjectResponse(BaseModel):
    id: UUID4
    name: str
    description: Optional[str]
    repo_url: str
    created_at: datetime
    updated_at: datetime
