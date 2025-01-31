from asyncpg.pool import Pool
import asyncpg
import os
from dotenv import load_dotenv


# Database connection parameters
DB_CONFIG = {
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432))
}

print(DB_CONFIG)

# Global pool variable
pool: Pool = None

async def init_db():
    """Initialize database pool"""
    global pool
    pool = await asyncpg.create_pool(**DB_CONFIG)
    return pool

async def close_db():
    """Close database pool"""
    if pool:
        await pool.close()

def get_pool() -> Pool:
    """Get database pool"""
    return pool
