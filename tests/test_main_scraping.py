#!/usr/bin/env python3
"""
Тест обновлённой функции run_scraping_stage.
"""
import asyncio
import sys
sys.path.insert(0, '.')
from main import run_scraping_stage
from config import ScraperConfig

async def main():
    isbns = ["9781835081167", "9780134173276", "9781805125105"]  # реальные ISBN из кэша
    config = ScraperConfig()
    config.verbose = True
    config.headless = False
    config.max_tabs = 2
    config.api_max_concurrent = 2
    print(f"Тестируем скрапинг для {len(isbns)} ISBN")
    results = await run_scraping_stage(isbns, [], config)
    print("Результаты:")
    for isbn, res in zip(isbns, results):
        if res:
            print(f"  {isbn}: {res.get('title')} ({res.get('source')})")
        else:
            print(f"  {isbn}: не найдено")

if __name__ == "__main__":
    asyncio.run(main())