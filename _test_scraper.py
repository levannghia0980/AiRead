import sys
import os

# Add backend directory to sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, "backend")
sys.path.insert(0, backend_dir)

import asyncio
import traceback
from app.services.crawler.plugins.shuba69 import Shuba69Scraper

async def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass  # Python version might not support it (unlikely)
        
    url = "https://www.69shuba.com/txt/83216/39104252"
    scraper = Shuba69Scraper()
    print(f"Analyzing URL: {url} ...")
    try:
        data = await scraper.get_novel_metadata(url)
        print("Success!")
        print("Title:", data.get("title"))
        print("Author:", data.get("author"))
        print("Genres:", data.get("genres"))
        print("Status:", data.get("status"))
        print("Number of chapters:", len(data.get("chapters", [])))
        if data.get("chapters"):
            print("First chapter URL:", data["chapters"][0]["url"])
            print("Last chapter URL:", data["chapters"][-1]["url"])
            print("Fetching chapter content...")
            ch_content = await scraper.get_chapter_content(data["chapters"][0]["url"])
            print("Chapter content length:", len(ch_content))
            print("Preview:\n", ch_content[:300])
    except Exception as e:
        print("Failed with exception:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
