import aiosqlite
from typing import AsyncGenerator

async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    db = await aiosqlite.connect("cache.db")
    db.row_factory = aiosqlite.Row  # optional: so results behave like dicts

    try:
        yield db
    finally:
        await db.close()
