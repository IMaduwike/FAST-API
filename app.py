from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import aiosqlite
from dotenv import load_dotenv
from routers.tiktok import router as tiktok_router
from routers.tiktok import file_router
from routers.anime import router as anime_router
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Just in case
        "https://your-production-domain.com"  # Add your production domain later
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)
app.include_router(tiktok_router)
app.include_router(anime_router)
app.include_router(file_router)
load_dotenv()
@app.on_event("startup")
async def startup():
    async with aiosqlite.connect("cache.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            filepath TEXT NOT NULL,
            short_code TEXT UNIQUE NOT NULL
        )
    """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS anime_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            episodes TEXT NOT NULL,
            internal_id TEXT NOT NULL UNIQUE,
            external_id TEXT NOT NULL UNIQUE
        )
    """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS anime_episode (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_count INTEGER,
            episode TEXT,
            external_id TEXT NOT NULL UNIQUE
        )
    """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS cached_video_url (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            internal_id TEXT NOT NULL,
            episode TEXT,
            video_url TEXT,
            size TEXT,
            snapshot TEXT,
            UNIQUE(internal_id, episode)
        )
    """)

        await db.commit()
@app.get(
    "/",
    tags=["fun"],
    summary="Download Tiktok",
    description="Returns a video url for the tiktok videos"
)
def say_hello():
    return "Hello world"

async def hello():
    return {
        "message":"Hello World"
    }