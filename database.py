import asyncpg
from typing import AsyncGenerator
import os
from contextlib import asynccontextmanager
import ssl

# Load DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Global pool reference
pool: asyncpg.Pool | None = None

# Supabase requires SSL
ssl_context = ssl.create_default_context()


async def init_db():
    """
    Initialize database connection pool and create required tables.
    Called on FastAPI startup.
    """
    global pool

    print("🔌 Connecting to PostgreSQL...")

    pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        ssl=ssl_context,     # REQUIRED for Supabase
        min_size=5,
        max_size=20,
        command_timeout=60
    )

    print("✅ PostgreSQL connected!")

    async with pool.acquire() as conn:
        print("📋 Creating tables...")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS download_sessions (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) UNIQUE NOT NULL,
                anime_title VARCHAR(255) NOT NULL,
                links JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

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
    """Close the database pool on shutdown."""
    global pool
    if pool:
        await pool.close()
        print("🔌 PostgreSQL connection closed")


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency for getting a connection from the pool."""
    async with pool.acquire() as conn:
        yield conn
