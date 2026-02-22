#!/usr/bin/env python3
import aiohttp
import asyncio
from api_clients import get_from_google_books_async


async def test():
    isbn = "9781835081167"
    async with aiohttp.ClientSession() as session:
        result = await get_from_google_books_async(session, isbn)
        print(f"Result: {result}")
        if result is None:
            # Попробуем сделать запрос вручную
            import requests

            resp = requests.get(
                "https://www.googleapis.com/books/v1/volumes",
                params={"q": f"isbn:{isbn}", "maxResults": 1},
            )
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.json()}")


asyncio.run(test())
