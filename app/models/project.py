from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProjectCreate(BaseModel):
    name: str
    repo_url: str
    repo_path: str
    default_branch: str
    current_branch: str
    last_commit: str
    description: Optional[str] = None

class Project(ProjectCreate):
    id: str
    created_at: datetime
    updated_at: datetime
