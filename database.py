import asyncpg
from typing import AsyncGenerator
import os
from contextlib import asynccontextmanager

# PostgreSQL connection details (use environment variables for security)
DATABASE_URL = os.getenv(
    "DATABASE_URL")

# Global connection pool
pool: asyncpg.Pool = None


async def init_db():
    """
    Initialize database connection pool and create tables
    Run this on startup!
    """
    global pool
    
    print("🔌 Connecting to PostgreSQL...")
    
    # Create connection pool
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=5,
        max_size=20,
        command_timeout=60
    )
    
    print("✅ PostgreSQL connected!")
    
    # Create tables
    async with pool.acquire() as conn:
        print("📋 Creating tables...")
        
        # Download sessions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS download_sessions (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) UNIQUE NOT NULL,
                anime_title VARCHAR(255) NOT NULL,
                links JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Analytics table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                anime_title VARCHAR(255),
                episode_count INTEGER,
                total_size VARCHAR(50),
                from_episode INTEGER,
                to_episode INTEGER,
                ip_address VARCHAR(50),
                user_agent TEXT,
                country VARCHAR(100),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better performance
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_type ON analytics(event_type)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anime_title ON analytics(anime_title)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON analytics(timestamp)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_id ON download_sessions(session_id)
        """)
        
        print("✅ Tables created successfully!")


async def close_db():
    """
    Close database connection pool
    Run this on shutdown!
    """
    global pool
    if pool:
        await pool.close()
        print("🔌 PostgreSQL connection closed")


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Dependency for getting database connection
    Use this in your FastAPI endpoints
    """
    async with pool.acquire() as conn:
        yield conn