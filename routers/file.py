import os
from fastapi import APIRouter, Query, HTTPException, Depends,Path
from fastapi import Query
from fastapi.responses import Response
from fastapi.responses import FileResponse
from db import get_db

file_router = APIRouter(prefix="/file",tags=["file"])
@file_router.get("/{code}")
async def get_file(
    code: str = Path(..., description="Code for given file"),
    db=Depends(get_db)
):
    # Query the file path
    cursor = await db.execute(
        "SELECT filepath FROM videos WHERE short_code = ?", (code,)
    )
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    file_path = row["filepath"]

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    filename = os.path.basename(file_path)

    # Return the file
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")


