import asyncio
import sys
import traceback
sys.path.append('g:\\05. GEM GEMINI 2026\\07_EcomOmniTool')
from backend.scraper import scraper

async def test():
    try:
        data = await scraper.scrape('https://www.tiktok.com/view/product/1735942865570006249')
        print("SUCCESS:", data)
    except Exception as e:
        print("ERROR_TYPE:", type(e))
        print("ERROR_STR:", repr(e))
        print("TRACEBACK:")
        traceback.print_exc()
        
    await scraper.close()

if __name__ == "__main__":
    asyncio.run(test())
