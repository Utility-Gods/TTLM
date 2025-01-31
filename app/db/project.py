from typing import Optional
from uuid import UUID
from .init import get_pool
from ..models.project import ProjectCreate


async def create_project(project: ProjectCreate) -> UUID:
    pool = get_pool()
    query = """
        INSERT INTO projects (name, description, repo_url)
        VALUES ($1, $2, $3)
        RETURNING id
    """
    async with pool.acquire() as conn:
        project_id = await conn.fetchval(
            query, project.name, project.description, project.repo_url
        )
        return project_id


async def get_project(project_id: UUID) -> Optional[dict]:
    pool = get_pool()
    query = "SELECT * FROM projects WHERE id = $1"
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, project_id)


async def get_all_projects():
    pool = get_pool()
    query = """
        SELECT id, name, repo_url, created_at, updated_at 
        FROM projects 
        ORDER BY created_at DESC
    """
    async with pool.acquire() as conn:
        return await conn.fetch(query)
