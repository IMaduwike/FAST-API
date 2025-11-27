import httpx
import asyncio
import time
from helpers.anime_helper import get_animepahe_cookies
async def test_animepahe_rate_limit():
    print("🧪 Testing animepahe rate limits...")
    
    # Get cookies once
    cookies = await get_animepahe_cookies()
    if not cookies:
        print("❌ Failed to get cookies")
        return
    
    print(f"✅ Got cookies: {cookies}\n")
    
    # Test with 50 requests
    success_count = 0
    fail_count = 0
    
    start_time = time.time()
    
    async with httpx.AsyncClient() as client:
        for i in range(50):
            try:
                response = await client.get(
                    "https://animepahe.si/api?m=search&q=naruto",
                    cookies=cookies,
                    timeout=10
                )
                
                if response.status_code == 200:
                    success_count += 1
                    print(f"✅ Request {i+1}/50: Success (200)")
                elif response.status_code == 429:
                    fail_count += 1
                    print(f"⚠️ Request {i+1}/50: Rate limited! (429)")
                elif response.status_code == 403:
                    fail_count += 1
                    print(f"🚫 Request {i+1}/50: Forbidden! (403)")
                else:
                    fail_count += 1
                    print(f"❌ Request {i+1}/50: Status {response.status_code}")
                
            except Exception as e:
                fail_count += 1
                print(f"❌ Request {i+1}/50: Error - {e}")
            
            # Very short delay (adjust if needed)
            await asyncio.sleep(0.1)
    
    elapsed = time.time() - start_time
    
    print(f"\n📊 Results:")
    print(f"✅ Successful: {success_count}/50")
    print(f"❌ Failed: {fail_count}/50")
    print(f"⏱️ Time taken: {elapsed:.2f} seconds")
    print(f"📈 Requests per second: {50/elapsed:.2f}")

# Run it
asyncio.run(test_animepahe_rate_limit())