import uuid
import json
import traceback
import io
import zipfile
import asyncio
from fastapi import APIRouter, Query, Depends,Request
from fastapi.responses import JSONResponse,StreamingResponse,Response
import httpx
from db import get_db
from helpers.anime_helper import get_pahewin_link,get_episode_session,get_kiwi_url,get_redirect_link
from helpers.anime_helper import get_animepahe_cookies,get_actual_episode,get_cached_anime_info
from utils.helper import generate_internal_id,encodeURIComponent
router = APIRouter(prefix="/anime", tags=["Anime"])
@router.get("/search", description="Searches for a specific anime", summary="Search anime")
async def anime_search(query: str = Query(..., description="Anime name for the search",example="one piece"),db = Depends(get_db)):
    if not query:
        return JSONResponse(status_code=400,content={
            "status":400,
            "message":"Query is a required parameter"
        })
    search_result = []
    try:
        cookies = await get_animepahe_cookies(db)
        async with httpx.AsyncClient(cookies=cookies,timeout=30) as client:
            encode_query = await encodeURIComponent(query)
            res = await client.get(f"https://animepahe.si/api?m=search&q={encode_query}")
        try:
            results = res.json()
        except ValueError:
            print("❌ Not a JSON response:", res.text[:200])  # show first part of the response for debugging
            return JSONResponse(status_code=500,content={
                "status":500,
                "message":"An error occured"
            })

        info = results.get('data')
        for i in info:
            cursor = await db.execute(
                "SELECT internal_id FROM anime_info WHERE external_id = ?", (i.get("session"),))
            row = await cursor.fetchone()
            episodes = await get_actual_episode(i.get("session"),db) if i.get(
                "episodes") == 0 or i.get("status") == "Currently Airing" else i.get("episodes")
            if not row:
                internal_id = await generate_internal_id(i.get("title"))
                await db.execute('''
                INSERT INTO anime_info(internal_id, external_id, title, episodes,poster)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(external_id) DO UPDATE SET
    title = excluded.title,
    episodes = excluded.episodes,
    poster = excluded.poster;

                ''',
                        (internal_id, i.get("session"), i.get("title"), episodes,i.get("poster")))
                await db.commit()
            else:
                internal_id = row["internal_id"]
            filtered_search_result = {
                "id": internal_id,
                "title": i.get("title"),
                "episodes": episodes,
                "status": i.get("status"),
                "year": i.get("year"),
                "poster": i.get("poster"),
                "rating": i.get("score")
            }
            search_result.append(filtered_search_result)
        return search_result
    except httpx.ConnectError:
        print("Connection error occured")
        traceback.print_exc()
        return JSONResponse(status_code=500,content={
            "status":500,
            "message":"Connection error occured Try again later"
        })
    except httpx.ConnectTimeout:
        print("Connection error occured")
        return JSONResponse(status_code=500,content={
            "status":500,
            "message":"Connection error occured Try again later"
        })

    except Exception as e:
        print("Anime search error: ",e)
        traceback.print_exc()
        return JSONResponse(status_code=500,content={
            "status":500,
            "message":"Internal Server error"
        })


        
@router.get("/download", description="Download anime using id gotten from search",summary="Download anime")
async def anime_download(id:str = Query(...,description="id for the anime from search",example="OP3526"),episode:int = Query(...,description="Anime episode number",example=6),quality: str = Query("720p", regex="^(360p|720p|1080p)$"),db= Depends(get_db)):
    if not id or not episode or not quality:
        return JSONResponse(status_code=400,content={
            "status":400,
            "message":"Id, episode or quality are required"
        })
    info = await get_cached_anime_info(id,db)
    if not info.get("status") == 200:
        return JSONResponse(
            status_code=info.get("status"),content={
                **info
            }
        )
    ep_count = info["episodes"]
    if int(episode) > int(ep_count):
        return JSONResponse(status_code=422,content={
            "status": 422,
            "message": "Episode number exceed available count"
        })
    if not info["external_id"]:
        return JSONResponse(status_code=404,content={
            "status": 404,
            "message": "No external id found"
        })
    if int(episode)<=0:
        return JSONResponse(status_code=400,content={
            "status":400,
            "message": "Episode count cannot be zero or below"
        })
    cursor = await db.execute(
        "SELECT * FROM cached_video_url WHERE internal_id = ? and episode = ? and quality = ?", (id, episode,quality))
    row = await cursor.fetchone()
    if row and row["video_url"]:
        link = row["video_url"]
        cursor2 = await db.execute("SELECT poster FROM anime_info WHERE internal_id = ?",(id,))
        row2 = await cursor2.fetchone()
        return {
                "status": 200,
                "direct_link": row["video_url"],
                "snapshot":row2["poster"],
                "quality":quality,
                "size": row["size"],
                "episode": row["episode"]
            }
    cursor = await db.execute("SELECT poster FROM anime_info WHERE internal_id = ?",(id,))
    row = await cursor.fetchone()
    if not row:
        return{
            "status":404,
            "message":"No image poster available"
        }
    search_result = await get_episode_session(info["external_id"],db)
    episode_info = search_result[int(episode)-1]
    episode_session = episode_info.get("session")
    episode_snapshot = row["poster"]
    pahe_link = await get_pahewin_link(info["external_id"], episode_session,db,quality)
    if pahe_link is None:
        return JSONResponse(status_code=404,content={
            "status": 404,
            "message": "Internal Link not found"
        })
    kiwi_url = await get_kiwi_url(pahe_link)
    results = await get_redirect_link(kiwi_url, id, episode,db,episode_snapshot,quality)
    if not results:
        return JSONResponse(status_code=500,content={
        "status": 500,
        "message": "Internal error: no results returned"
    })


    return JSONResponse(status_code=500 if results.get("status") == 500 else 200,content=results)

@router.get("/bulk-download", description="Bulk download multiple anime episodes", summary="Bulk download anime episodes")
async def anime_bulk_download(
    id: str = Query(..., description="ID for the anime from search", example="OP3526"),
    ep_from: int = Query(..., alias="from", description="Starting episode number", example=1, ge=1),
    ep_to: int = Query(..., alias="to", description="Ending episode number", example=24, ge=1),
    quality: str = Query("720p", regex="^(360p|720p|1080p)$"),
    db = Depends(get_db)
):
    # Validation
    if ep_from > ep_to:
        return JSONResponse(status_code=400, content={
            "status": 400,
            "message": "Starting episode cannot be greater than ending episode"
        })
    total_ep_count = ep_to - ep_from
    if total_ep_count >= 100:
        return JSONResponse(status_code=400,
        content= {
            "status":400,
            "message":"Limit reached. Must be less than 100 episodes."
        }
        )

    # Get anime info
    info = await get_cached_anime_info(id, db)
    if not info.get("status") == 200:
        return JSONResponse(
            status_code=info.get("status"),
            content={**info}
        )
    
    ep_count = info["episodes"]
    
    # Check if episodes are within range
    if ep_to > int(ep_count) or ep_from > int(ep_count):
        return JSONResponse(status_code=422, content={
            "status": 422,
            "episodes": ep_count,
            "message": "Episode number exceeds available count"
        })
    
    if not info["external_id"]:
        return JSONResponse(status_code=404, content={
            "status": 404,
            "message": "No external id found"
        })
    
    # Create list of episode numbers to fetch
    episodes = list(range(ep_from, ep_to + 1))
    # Fetch all episodes concurrently with asyncio.gather
    download_links = await asyncio.gather(*[
        _fetch_single_episode(id, episode, info["external_id"], db,quality)
        for episode in episodes
    ])
    
    # Filter out any None results (failed episodes)
    successful_links = [link for link in download_links if link is not None]
    
    if not successful_links:
        return JSONResponse(status_code=500, content={
            "status": 500,
            "message": "Failed to fetch any episode links"
        })
    
    # CREATE SESSION - Store links in DB
    session_id = str(uuid.uuid4())
    
    await db.execute(
        "INSERT INTO download_sessions (session_id, anime_id, anime_title, links, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
        (session_id, id, info.get("title", "Unknown"), json.dumps(successful_links))
    )
    await db.commit()
    
    
    return JSONResponse(status_code=200, content={
        "status": 200,
        "session_id": session_id,  # NEW: Return session ID
        "anime_title": info.get("title", "Unknown"),
        "total_requested": len(episodes),
        "total_fetched": len(successful_links),
        "links": successful_links
    })


async def _fetch_single_episode(id: str, episode: int, external_id: str, db,quality):
    """Helper function to fetch a single episode link"""
      # Only N requests at once
    try:
        # Check cache first
        cursor = await db.execute(
            "SELECT * FROM cached_video_url WHERE internal_id = ? and episode = ? and quality = ?", 
            (id, episode,quality)
        )
        row = await cursor.fetchone()
        
        if row and row["video_url"]:
            link = row["video_url"]
            
            try:
                return {
                        "episode": row["episode"],
                        "direct_link": row["video_url"],
                        "size": row["size"],
                        "snapshot": row["snapshot"],
                        "quality":quality,
                        "status": 200
                    }
            except Exception as e:
                print(f"⚠️ Episode {episode}: Cached link check failed ({e}), fetching fresh...")
        
        # Fetch fresh link
        
        # Add delay between requests
        await asyncio.sleep(0.5)
        
        search_result = await get_episode_session(external_id, db)
        episode_info = search_result[episode - 1]
        episode_session = episode_info.get("session")
        cursor2 = await db.execute("SELECT poster FROM anime_info WHERE internal_id = ?",(id,))
        row2 = await cursor2.fetchone()
        if not row2:
            return None
        episode_snapshot = row2["poster"]
        
        pahe_link = await get_pahewin_link(external_id, episode_session,db,quality)
        if not pahe_link:
            print(f"❌ Episode {episode}: No pahe link found")
            return None
        
        kiwi_url = await get_kiwi_url(pahe_link)
        if not kiwi_url:
            print(f"❌ Episode {episode}: No kiwi URL found")
            return None
        
        results = await get_redirect_link(kiwi_url, id, episode, db, episode_snapshot,quality)
        
        if results and results.get("status") == 200:
            return results
        else:
            print(f"❌ Episode {episode}: Failed to get redirect link")
            return None
            
    except Exception as e:
        print(f"❌ Episode {episode}: Error - {e}")
        import traceback
        traceback.print_exc()
        return None

import os
import json
import asyncio
import tempfile
import shutil
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import httpx
from fastapi import Query, Depends
from fastapi.responses import StreamingResponse, JSONResponse

@router.get("/bulk-download-zip")
async def bulk_download_zip_get(
    session_id: str = Query(..., description="Download session ID"),
    db = Depends(get_db)
):
    """
    Stream ZIP using temporary files with retry logic
    """
    
    # Get session
    cursor = await db.execute(
        "SELECT * FROM download_sessions WHERE session_id = ?",
        (session_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        return JSONResponse(status_code=404, content={"status": 404, "message": "Session not found"})
    
    links = json.loads(row["links"])
    anime_title = row["anime_title"].replace(" ", "_").lower()
    
    # Get episode range
    episodes = [int(link_info.get("episode")) for link_info in links if link_info.get("episode")]
    from_ep = min(episodes) if episodes else 1
    to_ep = max(episodes) if episodes else 1
    
    zip_filename = f"{anime_title}_{from_ep}-{to_ep}_episodes.zip"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://kwik.cx/',
    }
    
    async def download_with_retry(client, url, temp_file, episode, max_retries=3):
        """Download file with retry and resume support"""
        
        for attempt in range(max_retries):
            try:
                # Check if file exists (for resume)
                start_byte = 0
                if os.path.exists(temp_file):
                    start_byte = os.path.getsize(temp_file)
                    print(f"🔄 Resuming from {start_byte / 1024 / 1024:.2f} MB")
                
                # Add range header for resume
                download_headers = headers.copy()
                if start_byte > 0:
                    download_headers['Range'] = f'bytes={start_byte}-'
                
                # Download
                async with client.stream('GET', url, headers=download_headers, timeout=120.0) as response:
                    # Check if resume is supported
                    if start_byte > 0 and response.status_code not in [206, 200]:
                        print(f"⚠️ Resume not supported, starting fresh")
                        start_byte = 0
                        os.remove(temp_file) if os.path.exists(temp_file) else None
                        return await download_with_retry(client, url, temp_file, episode, max_retries - attempt)
                    
                    response.raise_for_status()
                    
                    # Get total size
                    content_length = response.headers.get('content-length')
                    total_size = int(content_length) if content_length else None
                    
                    # Open file in append mode if resuming
                    mode = 'ab' if start_byte > 0 else 'wb'
                    with open(temp_file, mode) as f:
                        downloaded = start_byte
                        last_print = 0
                        
                        async for chunk in response.aiter_bytes(chunk_size=1024*1024):
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Print progress every 50MB
                            if downloaded - last_print >= 50 * 1024 * 1024:
                                if total_size:
                                    progress = (downloaded / total_size) * 100
                                    print(f"📥 Episode {episode}: {downloaded / 1024 / 1024:.1f} MB / {total_size / 1024 / 1024:.1f} MB ({progress:.1f}%)")
                                else:
                                    print(f"📥 Episode {episode}: {downloaded / 1024 / 1024:.1f} MB")
                                last_print = downloaded
                    
                    print(f"✅ Downloaded Episode {episode} ({downloaded / 1024 / 1024:.2f} MB)")
                    return True
                    
            except (httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectError) as e:
                print(f"⚠️ Episode {episode} attempt {attempt + 1}/{max_retries} failed: {e}")
                
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                    print(f"⏳ Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"❌ Episode {episode} failed after {max_retries} attempts")
                    return False
                    
            except Exception as e:
                print(f"❌ Episode {episode} unexpected error: {e}")
                return False
        
        return False
    
    async def stream_zip():
        """Stream ZIP file with temp storage and retry logic"""
        temp_dir = None
        zip_path = None
        
        try:
            # Create temp directory
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, "output.zip")
            
            print(f"📁 Temp dir: {temp_dir}")
            
            # Track successful downloads
            successful_episodes = []
            
            # Download all episodes first
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=30.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            ) as client:
                for idx, link_info in enumerate(links, 1):
                    episode = link_info.get("episode")
                    url = link_info.get("direct_link")
                    
                    if not url:
                        continue
                    
                    temp_file = os.path.join(temp_dir, f"ep_{episode}.mp4")
                    
                    print(f"\n🎬 [{idx}/{len(links)}] Starting Episode {episode}...")
                    
                    success = await download_with_retry(client, url, temp_file, episode)
                    
                    if success:
                        successful_episodes.append({
                            'episode': episode,
                            'temp_file': temp_file,
                            'filename': f"{anime_title}_Episode_{str(episode).zfill(3)}.mp4"
                        })
                    else:
                        # Clean up failed download
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
            
            if not successful_episodes:
                raise Exception("No episodes downloaded successfully!")
            
            print(f"\n📦 Creating ZIP with {len(successful_episodes)} episodes...")
            
            # Create ZIP file
            with ZipFile(zip_path, 'w', ZIP_DEFLATED) as zipf:
                for ep_info in successful_episodes:
                    zipf.write(ep_info['temp_file'], ep_info['filename'])
                    print(f"📦 Added: {ep_info['filename']}")
                    # Delete temp file after adding to ZIP
                    os.remove(ep_info['temp_file'])
            
            zip_size = os.path.getsize(zip_path) / 1024 / 1024
            print(f"✨ ZIP created! Size: {zip_size:.2f} MB")
            print(f"✨ Successfully packed {len(successful_episodes)}/{len(links)} episodes")
            
            # Stream the ZIP file
            with open(zip_path, 'rb') as f:
                chunk_size = 1024 * 1024  # 1MB chunks
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    
        except Exception as e:
            print(f"💥 Fatal error: {e}")
            raise
            
        finally:
            # Cleanup temp files
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                print(f"🧹 Cleaned up temp dir")
    
    # Delete session
    await db.execute("DELETE FROM download_sessions WHERE session_id = ?", (session_id,))
    await db.commit()
    
    # Stream the ZIP
    return StreamingResponse(
        stream_zip(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "Content-Type": "application/zip"
        }
    )

@router.get("/proxy-image", description="Proxy images from animepahe")
async def proxy_image(
    url: str = Query(..., description="Image URL to proxy"), db= Depends(get_db)
):
    """
    Proxy images from animepahe with cookies to bypass 403
    """
    
    # Validate it's from animepahe (security)
    if "animepahe.si" not in url:
        return Response(status_code=400, content="Invalid image URL")
    
    try:
        # Get animepahe cookies
        cookies = await get_animepahe_cookies(db)
        
        # Fetch image with cookies
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, cookies=cookies)
        
        if response.status_code == 200:
            # Return image with proper content type
            return Response(
                content=response.content,
                media_type=response.headers.get("content-type", "image/jpeg"),
                headers={
                    "Cache-Control": "public, max-age=86400",  # Cache for 1 day
                }
            )
        else:
            # Return placeholder or 404
            return Response(status_code=response.status_code)
            
    except Exception as e:
        print(f"Error proxying image: {e}")
        return Response(status_code=500)