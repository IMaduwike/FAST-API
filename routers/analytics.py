from datetime import datetime, timedelta
from fastapi import Request, Depends
import httpx
from database import get_db
from fastapi import APIRouter

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.post("/track")
async def track_analytics(
    request: Request,
    db = Depends(get_db)
):
    """Track user activity"""
    
    # Get JSON body
    try:
        body = await request.json()
    except:
        return {"status": "error", "message": "Invalid JSON"}
    
    event_type = body.get("event_type")
    anime_title = body.get("anime_title")
    episode_count = body.get("episode_count")
    total_size = body.get("total_size")
    from_episode = body.get("from_episode")
    to_episode = body.get("to_episode")
    
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Get country from IP (optional)
    country = "Unknown"
    try:
        async with httpx.AsyncClient() as client:
            geo_response = await client.get(f"http://ip-api.com/json/{ip_address}", timeout=2)
            if geo_response.status_code == 200:
                geo_data = geo_response.json()
                country = geo_data.get("country", "Unknown")
    except:
        pass
    
    # Insert into database
    await db.execute("""
        INSERT INTO analytics 
        (event_type, anime_title, episode_count, total_size, from_episode, to_episode, 
         timestamp, ip_address, user_agent, country)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    """, event_type, anime_title, episode_count, total_size, from_episode, to_episode,
          datetime.now(), ip_address, user_agent, country)
    
    return {"status": "ok"}

@router.get("/stats")
async def get_analytics_stats(
    days: int = 7,  # Last 7 days by default
    db = Depends(get_db)
):
    """Get analytics statistics"""
    
    start_date = datetime.now() - timedelta(days=days)
    
    # Total visits (use fetchval for single value)
    total_visits = await db.fetchval(
        "SELECT COUNT(*) FROM analytics WHERE event_type = 'visit' AND timestamp >= $1",
        start_date
    ) or 0
    
    # Total searches
    total_searches = await db.fetchval(
        "SELECT COUNT(*) FROM analytics WHERE event_type = 'search' AND timestamp >= $1",
        start_date
    ) or 0
    
    # Total downloads
    total_downloads = await db.fetchval(
        "SELECT COUNT(*) FROM analytics WHERE event_type = 'download' AND timestamp >= $1",
        start_date
    ) or 0
    
    # Total episodes downloaded
    total_episodes = await db.fetchval(
        "SELECT COALESCE(SUM(episode_count), 0) FROM analytics WHERE event_type = 'download' AND timestamp >= $1",
        start_date
    ) or 0
    
    # Most searched anime (use fetch for multiple rows)
    top_searches_rows = await db.fetch("""
        SELECT anime_title, COUNT(*) as count 
        FROM analytics 
        WHERE event_type = 'search' 
        AND anime_title IS NOT NULL 
        AND timestamp >= $1
        GROUP BY anime_title 
        ORDER BY count DESC 
        LIMIT 10
    """, start_date)
    top_searches = [dict(row) for row in top_searches_rows]
    
    # Most downloaded anime
    top_downloads_rows = await db.fetch("""
        SELECT 
            anime_title, 
            COUNT(*) as download_count,
            SUM(episode_count) as total_episodes,
            string_agg(DISTINCT CONCAT(from_episode::text, '-', to_episode::text), ', ') as episode_ranges
        FROM analytics 
        WHERE event_type = 'download' 
        AND anime_title IS NOT NULL 
        AND timestamp >= $1
        GROUP BY anime_title 
        ORDER BY download_count DESC 
        LIMIT 10
    """, start_date)
    top_downloads = [dict(row) for row in top_downloads_rows]
    
    # Daily visits chart data
    daily_visits_rows = await db.fetch("""
        SELECT 
            DATE(timestamp) as date,
            COUNT(*) as visits
        FROM analytics 
        WHERE event_type = 'visit' 
        AND timestamp >= $1
        GROUP BY DATE(timestamp)
        ORDER BY date ASC
    """, start_date)
    daily_visits = [dict(row) for row in daily_visits_rows]
    
    # Countries
    top_countries_rows = await db.fetch("""
        SELECT 
            country,
            COUNT(*) as count
        FROM analytics 
        WHERE timestamp >= $1 AND country != 'Unknown'
        GROUP BY country 
        ORDER BY count DESC 
        LIMIT 10
    """, start_date)
    top_countries = [dict(row) for row in top_countries_rows]
    
    return {
        "period_days": days,
        "total_visits": total_visits,
        "total_searches": total_searches,
        "total_downloads": total_downloads,
        "total_episodes": total_episodes,
        "top_searches": top_searches,
        "top_downloads": top_downloads,
        "daily_visits": daily_visits,
        "top_countries": top_countries
    }