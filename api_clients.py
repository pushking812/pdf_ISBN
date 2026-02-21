import aiohttp
import re
import re
from typing import Any, Optional, Dict


async def get_from_google_books_async(
    session: aiohttp.ClientSession, isbn: str
) -> Optional[Dict[str, Any]]:
    """Асинхронный клиент Google Books API."""
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": f"isbn:{isbn}", "maxResults": 1}
    try:
        async with session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            if response.status == 429:
                import sys
                sys.stderr.write(
                    f"[WARNING] Google Books API quota exceeded for ISBN {isbn}. "
                    "No results will be returned until quota resets.\n"
                )
                return None
            response.raise_for_status()
            data = await response.json()
            if data.get("totalItems", 0) == 0:
                return None
            volume = data["items"][0]["volumeInfo"]
            title = volume.get("title", "Нет названия")
            authors = volume.get("authors", ["Неизвестный автор"])

            pages = volume.get("pageCount")
            if pages is not None:
                pages = str(pages)
            else:
                pages = None

            year = None
            published_date = volume.get("publishedDate")
            if published_date:
                match = re.search(r"\d{4}", published_date)
                if match:
                    year = match.group()

            return {
                "title": title,
                "authors": authors,
                "source": "Google Books",
                "pages": pages,
                "year": year,
            }
    except (aiohttp.ClientError, KeyError, IndexError, ValueError):
        return None


async def get_from_open_library_async(
    session: aiohttp.ClientSession, isbn: str
) -> Optional[Dict[str, Any]]:
    """Асинхронный клиент Open Library API."""
    url = "https://openlibrary.org/api/books"
    params = {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"}
    headers = {"User-Agent": "BookSearcher/1.0 (contact@example.com)"}
    try:
        async with session.get(
            url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            response.raise_for_status()
            data = await response.json()
            key = f"ISBN:{isbn}"
            if key not in data:
                return None
            book_data = data[key]
            title = book_data.get("title", "Нет названия")
            authors = [a["name"] for a in book_data.get("authors", [])]
            if not authors:
                authors = ["Неизвестный автор"]

            year = None
            if "publish_date" in book_data:
                m = re.search(r"\d{4}", book_data["publish_date"])
                if m:
                    year = m.group()

            pages = book_data.get("number_of_pages")
            if pages is not None:
                pages = str(pages)

            return {
                "title": title,
                "authors": authors,
                "source": "Open Library",
                "pages": pages,
                "year": year,
            }
    except (aiohttp.ClientError, KeyError, ValueError):
        return None
