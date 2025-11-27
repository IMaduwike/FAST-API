import json
import os
import re
import secrets
from datetime import datetime
import asyncio
import yt_dlp
from yt_dlp.utils import DownloadError
# from db import get_db

def raw_video_downloader(url):
    try:
        os.makedirs("downloads", exist_ok=True)

        # Get video info first
        with yt_dlp.YoutubeDL({"quiet": True}) as yt:
            info = yt.extract_info(url, download=False)

        PROJECT_URL = os.getenv('PROJECT_URL')
        title = info.get("title", "video")

        # Clean title
        title = re.sub(r"[^\w\s-]", "", title)
        title = title.strip().replace(" ", "_")
        title = title[:40]  # shorten to 40 chars

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_path = os.path.join("downloads", f"{title}_{timestamp}.mp4")

        # Download directly - force H.264 codec
        options = {
            "format": "bestvideo[vcodec^=avc1]+bestaudio/best",
            "outtmpl": final_path,
            "quiet": False,
            "nocheckcertificate": True,
            "retries": 10,
            "fragment_retries": 10,
            "noprogress": True
        }
        
        with yt_dlp.YoutubeDL(options) as yt:
            yt.download([url])

        # Generate short code + DB insert
        short_code = secrets.token_urlsafe(6)
        dlurl = PROJECT_URL if PROJECT_URL else "http://localhost:8000"
        return {
            "status":200,
            "channel_info": {
                "channel_name": info.get("channel"),
                "channel_url": info.get("channel_url")
            },
            "video_info": {
                "title": info.get("title"),
                "comment_count": info.get("comment_count"),
                "description": info.get("description"),
                "like_count": info.get("like_count")
            },
            "download_url": dlurl+f"/file/{short_code}",
            "short":short_code,
            "path":final_path
        }
    except DownloadError as e:
        print("An error occured while downloading",e)
        if "Unsupported URL" in str(e):
            return{
                "status":422,
                "message":"Unsupported Url"
            }
        else:
            return {
            "status":500,
            "message":"Internal Server error"
        }
    except Exception as e:
        print("Error downloading:", e)
        return {
            "status":500,
            "message":"Internal Server error"
        }
def raw_video_downloader_for_insta(url):
    try:
        os.makedirs("downloads", exist_ok=True)

        # Get video info first
        with yt_dlp.YoutubeDL({"quiet": True}) as yt:
            info = yt.extract_info(url, download=False)

        PROJECT_URL = os.getenv('PROJECT_URL')
        title = info.get("title", "video")

        # Clean title
        title = re.sub(r"[^\w\s-]", "", title)
        title = title.strip().replace(" ", "_")
        title = title[:40]  # shorten to 40 chars

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_path = os.path.join("downloads", f"{title}_{timestamp}.mp4")

        # Download directly - force H.264 codec
        options = {
            "format": "bestvideo[vcodec^=avc1]+bestaudio/best",
            "outtmpl": final_path,
            "quiet": False,
            "nocheckcertificate": True,
            "retries": 10,
            "cookiesfrombrowser": ("brave",),
            'cookiefile': './insta_cookies.txt',
            "fragment_retries": 10,
            "noprogress": True
        }
        
        with yt_dlp.YoutubeDL(options) as yt:
            yt.download([url])

        # Generate short code + DB insert
        short_code = secrets.token_urlsafe(6)
        dlurl = PROJECT_URL if PROJECT_URL else "http://localhost:8000"
        return {
            "status":200,
            "channel_info": {
                "channel_name": info.get("channel"),
                "channel_url": info.get("channel_url")
            },
            "video_info": {
                "title": info.get("title"),
                "comment_count": info.get("comment_count"),
                "description": info.get("description"),
                "like_count": info.get("like_count")
            },
            "download_url": dlurl+f"/file/{short_code}",
            "short":short_code,
            "path":final_path
        }
    except DownloadError as e:
        print("An error occured while downloading",e)
        if "Unsupported URL" in str(e):
            return{
                "status":422,
                "message":"Unsupported Url"
            }
        else:
            return {
            "status":500,
            "message":"Internal Server error"
        }
    except Exception as e:
        print("Error downloading:", e)
        return {
            "status":500,
            "message":"Internal Server error"
        }

async def videoDL(url,db):
    info = await asyncio.to_thread(raw_video_downloader,url)
    if not info or info.get("status") == 500:
        return info
    if not info or info.get("status") == 400:
        return info
    await db.execute(
        "INSERT INTO videos (title, filepath, short_code) VALUES (?, ?, ?)",
        (info["video_info"]["title"], info["path"], info["short"])
    )
    await db.commit()
    return info
async def videoDL_for_insta(url,db):
    info = await asyncio.to_thread(raw_video_downloader_for_insta,url)
    if not info or info.get("status") == 500:
        return info
    if not info or info.get("status") == 400:
        return info
    await db.execute(
        "INSERT INTO videos (title, filepath, short_code) VALUES (?, ?, ?)",
        (info["video_info"]["title"], info["path"], info["short"])
    )
    await db.commit()
    return info