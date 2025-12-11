import json
import asyncio
import time
import os
import re
from bs4 import BeautifulSoup
import httpx
from playwright.async_api import async_playwright,TimeoutError
from utils.helper import deobfuscate,extract_info

async def cookies_expired(db):
    """Check if __ddg2 cookie is expired"""
    now = time.time()
    
    cursor = await db.execute(
        "SELECT value, expires FROM cookies WHERE name = ?", 
        ("__ddg2",)
    )
    row = await cursor.fetchone()
    
    if not row:
        print(f"❌ __ddg2 cookie missing from database")
        return True
    
    exp = row["expires"]
    if not exp:
        print(f"❌ __ddg2 has no expiry field")
        return True
    
    is_expired = exp < now
    return is_expired


async def get_animepahe_cookies(db):
    """Get cookies from SQLite database, refresh if expired"""
    
    # 1️⃣ Check if cached cookies exist and are still valid
    cursor = await db.execute("SELECT COUNT(*) as count FROM cookies")
    row = await cursor.fetchone()
    
    if row["count"] > 0:
        if not await cookies_expired(db):
            
            # Fetch all cookies
            cursor = await db.execute("SELECT name, value FROM cookies")
            rows = await cursor.fetchall()
            return {row["name"]: row["value"] for row in rows}
        else:
            print("⚠️ Cookies expired, fetching new ones...")
    
    # 2️⃣ Cookies expired or don't exist - use Playwright
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Go to Animepahe
            await page.goto("https://animepahe.si")
            
            # Wait for main content to load
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
            except TimeoutError:
                print("⚠️ Timeout waiting for DOMContentLoaded, continuing anyway...")
            
            # Small sleep to ensure cookies are set
            await asyncio.sleep(1)
            
            cookies = await context.cookies()
            await browser.close()
            
            # Clear old cookies and insert new ones
            await db.execute("DELETE FROM cookies")
            
            for cookie in cookies:
                await db.execute(
                    "INSERT INTO cookies (name, value, expires) VALUES (?, ?, ?)",
                    (cookie['name'], cookie['value'], cookie.get('expires'))
                )
            
            await db.commit()
            
            print("✅ Used fresh cookies from animepahe server")
            
            # Return cookies as dict
            return {c['name']: c['value'] for c in cookies}
            
    except Exception as e:
        print(f"❌ Failed to get new cookies: {e}")
        
        # Fallback: return cached cookies even if expired (better than nothing)
        cursor = await db.execute("SELECT name, value FROM cookies")
        rows = await cursor.fetchall()
        
        if rows:
            print("⚠️ Using expired cached cookies as fallback")
            return {row["name"]: row["value"] for row in rows}
        
        return None  # No cookies available at all

async def get_actual_episode(external_id,db):
    try:
        if not external_id:
            return None
        cookies = await get_animepahe_cookies(db)
        
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"https://animepahe.si/api?m=release&id={external_id}",
                cookies=cookies,
                timeout=30
            )
        if res.status_code != 200:
            return None
        data = res.json()

        return data.get("total")
    except httpx.ConnectTimeout:
        print("Connection error")
        return None
    except Exception as e:
        print(e)
        return None

async def get_cached_anime_info(id, db):
    try:
        if not id:
            return {"status": 400, "message": "No ID provided"}
        
        if not db:
            return {"status": 500, "message": "Database connection required"}
        
        cursor = await db.execute("SELECT * FROM anime_info WHERE internal_id = ?", (id,))
        row = await cursor.fetchone()
        
        if not row:
            return {"status": 404, "message": "Anime not found in cache"}
        
        # Check if external_id exists
        external_id = row["external_id"]
        if not external_id:
            return {"status": 400, "message": "No external_id found for this anime"}
        
        # Get actual episode count
        episodes = await get_actual_episode(external_id,db)
        
        if not episodes:
            return {"status": 500, "message": "Failed to fetch episode count"}
        
        # Update if episode count changed
        if int(episodes) != int(row["episodes"]):
            await db.execute(
                "UPDATE anime_info SET episodes = ? WHERE internal_id = ?",
                (episodes, id)
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM anime_info WHERE internal_id = ?", (id,))
            row = await cursor.fetchone()
        if not row:
            return {"status":404,"message":"Id not registered. Search the anime first"}
        return {"status": 200, **row}
    
    except Exception as e:
        print(f"Error in get_cached_anime_info: {e}")
        traceback.print_exc()
        return {"status": 500, "message": f"Internal error: {str(e)}"}

async def get_episode_session(id, db):
    if not id:
        return None
    
    cookies = await get_animepahe_cookies(db)
    
async def get_episode_session(id,db):
    if not id:
        return None
    cookies = await get_animepahe_cookies(db)
    async with httpx.AsyncClient(cookies=cookies) as client:
        res = await client.get(f"https://animepahe.si/api?m=release&id={id}")
        data = res.json()
        if not data:
            return {
                "status":404,
                "message":"Anime episodes not found"
            }
        episode_id = data.get("data")[0].get("session")
        url = f"https://animepahe.si/play/{id}/{episode_id}"
        res = await client.get(url,cookies=cookies)
    episode_session = await asyncio.to_thread(_parse_episode_html,res.text)
    return episode_session

def _parse_episode_html(content):
    soup = BeautifulSoup(content,"html.parser")
    div = soup.find("div",id="scrollArea")
    if not div:
        return {
            "status":404,
            "message":"No scroll Area found"
        }
    
    a_tags = div.find_all("a",class_="dropdown-item")
    episode_session = []
    for a_tag in a_tags:
        episode_dict= {
            "session":a_tag["href"].split("/")[3],
            "episode":int(a_tag.text.split(" ")[1])
        }
        episode_session.append(episode_dict)
    return episode_session

async def get_pahewin_link(external_id, episode_id,db,quality):
    if not episode_id or not external_id:
        return None
    
    url = f"https://animepahe.si/play/{external_id}/{episode_id}"
    cookies = await get_animepahe_cookies(db)
    
    # Use httpx for async HTTP request
    async with httpx.AsyncClient() as client:
        res = await client.get(url, cookies=cookies, timeout=10)
        html = res.text
    
    # Offload BeautifulSoup parsing to thread pool
    link = await asyncio.to_thread(_parse_pahewin_html, html, url,quality)
    return link


def _parse_pahewin_html(html, url, quality="720p"):
    soup = BeautifulSoup(html, "html.parser")
    dropdown = soup.find("div", id="pickDownload")
    if not dropdown:
        return None
    
    links = dropdown.find_all("a", class_="dropdown-item")
    
    # Get all available qualities with their links
    available = []
    for a in links:
        text = a.get_text(" ", strip=True).lower()
        if "eng" not in text:  # Skip English dubs
            # Extract resolution (360, 720, 1080, 400, 800, etc.)
            match = re.search(r'(\d+)p', text)
            if match:
                resolution = int(match.group(1))
                available.append({
                    "resolution": resolution,
                    "link": a["href"],
                    "text": text
                })
    
    if not available:
        return None
    
    # Find closest match to requested quality
    target = int(quality.replace("p", ""))
    closest = min(available, key=lambda x: abs(x["resolution"] - target))
    
    return closest["link"]

async def get_kiwi_url(pahe_url):
    if not pahe_url:
        print("No pahe.win link")
        return None
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "*/*"
    }

    # Async HTTP request with httpx
    async with httpx.AsyncClient() as client:
        res = await client.get(pahe_url, timeout=30, headers=headers)
        html = res.text
    
    # Offload BeautifulSoup parsing to thread pool
    return await asyncio.to_thread(_parse_kiwi_url, html)


def _parse_kiwi_url(html):
    """Synchronous HTML parsing - runs in thread pool"""
    soup = BeautifulSoup(html, "html.parser")
    info = soup.find("script")
    if not info or "kwik" not in info.text:
        return None
    m = re.search(r"https?://(?:www\.)?kwik\.cx[^\s\"');]+", info.text)
    return m.group(0) if m else None

async def get_kiwi_info(kiwi_url):
    try:
        if not kiwi_url:
            return None
        
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131 Safari/537.36',
        }

        # Async HTTP request with httpx
        async with httpx.AsyncClient() as client:
            res = await client.get(kiwi_url, timeout=10, headers=headers)
            html = res.text
            cookies = res.cookies
        
        # Offload CPU-bound parsing/deobfuscation to thread pool
        result = await asyncio.to_thread(_parse_and_deobfuscate_kiwi, html, cookies)
        return result
        
    except IndexError:
        print(html)
        print("Script is out of range -2")
        return None
    except Exception as e:
        print("Kiwi error Occured", e)
        traceback.print_exc()
        return None

def _parse_and_deobfuscate_kiwi(html, cookies):
    """Synchronous parsing and deobfuscation - runs in thread pool"""
    html_soup = BeautifulSoup(html, "html.parser")
    scripts = html_soup.find_all("script")
    obf_js = scripts[-3].text
    deobf_js = deobfuscate(obf_js)
    
    return {
        **extract_info(deobf_js),
        "kwik_session": cookies.get("kwik_session")
    }

async def get_redirect_link(url, id, episode, db,snapshot,quality):
    if not url or not id or not episode:
        print("No url,episode or id detected ending now")
        return None
    
    info = await get_kiwi_info(url)
    if not info:
        return {
            "status": 500,
            "message": "Server timed out, retry request"
        }
    
    base_url = "https://kwik-test.vercel.app/kwik"
    # base_url = "http://localhost:5000/kwik"
    payload = {
        "kwik_url": url,
        "token": info.get("token"),
        "kwik_session": info.get("kwik_session")
    }
    
    # Async HTTP POST with httpx
    async with httpx.AsyncClient() as client:
        res = await client.post(
            base_url,
            content=json.dumps(payload),
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
    
    if res.status_code != 200:
        print(res.text)
        return {
            "status": 500,
            "message": "Server timed out"
        }
    
    data = res.json()
    size = info.get("size")
    direct_link = data.get("download_link")
    
    # Async database operations
    await db.execute(
        "INSERT OR REPLACE INTO cached_video_url(internal_id,episode,video_url,size,snapshot,quality) VALUES(?,?,?,?,?,?)",
        (id, episode, direct_link, size,snapshot,quality)
    )
    await db.commit()
    return {
        "direct_link": direct_link,
        "episode": episode,
        "snapshot": snapshot,
        "quality":quality,
        "status": 200,
        "size": size
    }