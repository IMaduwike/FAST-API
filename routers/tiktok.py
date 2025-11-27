import os
from fastapi import APIRouter, Query, HTTPException, Depends,Path
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from utils.helper import check_platform
from helpers.download import videoDL,videoDL_for_insta
from db import get_db

router = APIRouter(prefix="/dl", tags=["downloaders"])
file_router = APIRouter(prefix="/file",tags=["file"])


@router.get("/tiktok",
            description="A tiktok downloader route that returns video info and download url for each video.",
            summary="Download Tiktok"
            )
async def tiktok_DL(url: str = Query(..., description="tiktok url", example="https://vm.tiktok.com/XXXXX"), db=Depends(get_db)):
    if not url:
        return JSONResponse(status_code=400, content={
            "status": 400,
            "message": "Url is required"
        })
    platform = await check_platform(url)
    if platform != "tiktok":
        return JSONResponse(status_code=400, content={
            "status": 400,
            "message": "Not a valid tiktok link"
        })

    info = await videoDL(url, db)
    if info.get("status") == 422:
        return JSONResponse(status_code=422, content={
                            **info} if info else {"message": "No info available"})
    if info.get("status") == 500:
        return JSONResponse(status_code=500, content={
                            **info} if info else {"message": "No info available"})
    info.pop("path",None)
    info.pop("short",None)
    return info
@router.get("/insta",
            description="A instagram downloader route that returns video info and download url for each video.",
            summary="Download instagram"
            )
async def instagram_DL(url: str = Query(..., description="instagram url", example="https://www.instagram.com/XXXXX"), db=Depends(get_db)):
    if not url:
        return JSONResponse(status_code=400, content={
            "status": 400,
            "message": "Url is required"
        })
    platform = await check_platform(url)
    if platform != "instagram":
        return JSONResponse(status_code=400, content={
            "status": 400,
            "message": "Not a valid instagram link"
        })

    info = await videoDL_for_insta(url, db)
    if info.get("status") == 422:
        return JSONResponse(status_code=422, content={
                            **info} if info else {"message": "No info available"})
    if info.get("status") == 500:
        return JSONResponse(status_code=500, content={
                            **info} if info else {"message": "No info available"})
    info.pop("path",None)
    info.pop("short",None)
    return info
@router.get("/fb",
            description="A facebook downloader route that returns video info and download url for each video.",
            summary="Download facebook"
            )
async def facebook_DL(url: str = Query(..., description="facebook url", example="https://www.facebook.com/XXXXX"), db=Depends(get_db)):
    if not url:
        return JSONResponse(status_code=400, content={
            "status": 400,
            "message": "Url is required"
        })
    platform = await check_platform(url)
    if platform != "facebook":
        return JSONResponse(status_code=400, content={
            "status": 400,
            "message": "Not a valid facebook link"
        })

    info = await videoDL(url, db)
    if info.get("status") == 422:
        return JSONResponse(status_code=422, content={
                            **info} if info else {"message": "No info available"})
    if info.get("status") == 500:
        return JSONResponse(status_code=500, content={
                            **info} if info else {"message": "No info available"})
    info.pop("path",None)
    info.pop("short",None)
    return info
@router.get("/yt",
            description="A youtube downloader route that returns video info and download url for each video.",
            summary="Download youtube"
            )
async def youtube_DL(url: str = Query(..., description="youtube url", example="https://www.youtube.com/XXXXX"), db=Depends(get_db)):
    if not url:
        return JSONResponse(status_code=400, content={
            "status": 400,
            "message": "Url is required"
        })
    platform = await check_platform(url)
    if platform != "youtube":
        return JSONResponse(status_code=400, content={
            "status": 400,
            "message": "Not a valid youtube link"
        })

    info = await videoDL(url, db)
    if info.get("status") == 422:
        return JSONResponse(status_code=422, content={
                            **info} if info else {"message": "No info available"})
    if info.get("status") == 500:
        return JSONResponse(status_code=500, content={
                            **info} if info else {"message": "No info available"})
    info.pop("path",None)
    info.pop("short",None)
    return info
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