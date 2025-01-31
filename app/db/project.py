from typing import Optional
from uuid import UUID
import logging
from .init import get_pool
from ..models.project import ProjectCreate

logger = logging.getLogger(__name__)

async def create_project(project: ProjectCreate) -> UUID:
    pool = get_pool()
    query = """
        INSERT INTO projects (
            name, 
            description, 
            repo_url,
            repo_path,
            default_branch,
            current_branch,
            last_commit
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
    """
    async with pool.acquire() as conn:
        try:
            project_id = await conn.fetchval(
                query,
                project.name,
                project.description,
                project.repo_url,
                project.repo_path,
                project.default_branch,
                project.current_branch,
                project.last_commit
            )
            logger.info(f"Created project {project.name} with ID {project_id}")
            return project_id
        except Exception as e:
            logger.error(f"Failed to create project {project.name}: {str(e)}")
            raise

async def get_project(project_id: UUID) -> Optional[dict]:
    pool = get_pool()
    query = """
        SELECT 
            id, 
            name, 
            description, 
            repo_url,
            repo_path,
            default_branch,
            current_branch,
            last_commit,
            created_at,
            updated_at
        FROM projects 
        WHERE id = $1
    """
    async with pool.acquire() as conn:
        try:
            return await conn.fetchrow(query, project_id)
        except Exception as e:
            logger.error(f"Failed to fetch project {project_id}: {str(e)}")
            raise

async def get_all_projects():
    pool = get_pool()
    query = """
        SELECT 
            id, 
            name, 
            repo_url,
            repo_path,
            default_branch,
            current_branch,
            last_commit,
            created_at, 
            updated_at 
        FROM projects 
        ORDER BY created_at DESC
    """
    async with pool.acquire() as conn:
        try:
            projects = await conn.fetch(query)
            logger.info(f"Retrieved {len(projects)} projects")
            return projects
        except Exception as e:
            logger.error(f"Failed to fetch projects: {str(e)}")
            raise

async def update_project_branch(project_id: UUID, branch: str, commit: str) -> bool:
    pool = get_pool()
    query = """
        UPDATE projects 
        SET current_branch = $2, 
            last_commit = $3,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = $1
    """
    async with pool.acquire() as conn:
        try:
            result = await conn.execute(query, project_id, branch, commit)
            logger.info(f"Updated project {project_id} to branch {branch} at commit {commit}")
            return True
        except Exception as e:
            logger.error(f"Failed to update project {project_id} branch: {str(e)}")
            raise
