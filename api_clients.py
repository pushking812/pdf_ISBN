import aiohttp
import re
from typing import Any, Optional, Dict
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from utils import normalize_isbn


async def get_from_google_books_async(session: aiohttp.ClientSession, isbn: str) -> Optional[Dict[str, Any]]:
    """Асинхронный поиск книги в Google Books API по ISBN."""
    norm_isbn = normalize_isbn(isbn)
    if not norm_isbn:
        return None
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": f"isbn:{norm_isbn}", "maxResults": 1}
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
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
                match = re.search(r'\d{4}', published_date)
                if match:
                    year = match.group()

            return {
                "title": title,
                "authors": authors,
                "source": "Google Books",
                "pages": pages,
                "year": year
            }
    except (aiohttp.ClientError, KeyError, IndexError, ValueError):
        return None


async def get_from_open_library_async(session: aiohttp.ClientSession, isbn: str) -> Optional[Dict[str, Any]]:
    """Асинхронный поиск книги в Open Library API по ISBN."""
    norm_isbn = normalize_isbn(isbn)
    if not norm_isbn:
        return None
    url = "https://openlibrary.org/api/books"
    params = {
        "bibkeys": f"ISBN:{norm_isbn}",
        "format": "json",
        "jscmd": "data"
    }
    headers = {"User-Agent": "BookSearcher/1.0 (contact@example.com)"}
    try:
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            response.raise_for_status()
            data = await response.json()
            key = f"ISBN:{norm_isbn}"
            if key not in data:
                return None
            book_data = data[key]
            title = book_data.get("title", "Нет названия")
            authors = [a["name"] for a in book_data.get("authors", [])]
            if not authors:
                authors = ["Неизвестный автор"]

            year = None
            if "publish_date" in book_data:
                m = re.search(r'\d{4}', book_data["publish_date"])
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
                "year": year
            }
    except (aiohttp.ClientError, KeyError, ValueError):
        return None


async def get_from_rsl_async(session: aiohttp.ClientSession, isbn: str) -> Optional[Dict[str, Any]]:
    """
    Асинхронный поиск книги в Российской государственной библиотеке (РГБ) по ISBN.
    Парсит HTML-страницу результатов поиска.
    """
    url = "https://search.rsl.ru/ru/search"
    params = {"q": isbn}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
            response.raise_for_status()
            html = await response.text()
            soup = BeautifulSoup(html, 'lxml')

            containers = soup.find_all('div', class_='search-container')
            if not containers:
                return None

            first = containers[0]

            author_tag = first.find('b', class_='js-item-authorinfo')
            authors = []
            if author_tag:
                authors = [author_tag.text.strip().rstrip('.')]
            else:
                authors = ["Неизвестный автор"]

            desc_span = first.find('span', class_='js-item-maininfo')
            if not desc_span:
                return None
            description = desc_span.text.strip()

            title = description.split(' / ')[0].strip()
            if not title:
                title = "Не удалось определить название"

            year = None
            year_match = re.search(r',\s*(\d{4})[\.\s\(]', description)
            if year_match:
                year = year_match.group(1)

            pages = None
            pages_match = re.search(r'\.\s*-\s*(\d+)\s+с\.', description)
            if pages_match:
                pages = pages_match.group(1)

            return {
                "title": title,
                "authors": authors,
                "source": "РГБ",
                "pages": pages or "не указано",
                "year": year or "не указан"
            }
    except Exception:
        return None


def get_from_google_books(isbn: str) -> Optional[Dict[str, Any]]:
    """Синхронный поиск книги в Google Books API по ISBN с извлечением года и страниц."""
    norm_isbn = normalize_isbn(isbn)
    if not norm_isbn:
        return None
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": f"isbn:{norm_isbn}", "maxResults": 1}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
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
            match = re.search(r'\d{4}', published_date)
            if match:
                year = match.group()

        return {
            "title": title,
            "authors": authors,
            "source": "Google Books",
            "pages": pages,
            "year": year
        }
    except (RequestException, KeyError, IndexError, ValueError):
        return None


def get_from_open_library(isbn: str) -> Optional[Dict[str, Any]]:
    """Синхронный поиск книги в Open Library API по ISBN с извлечением года и страниц."""
    norm_isbn = normalize_isbn(isbn)
    if not norm_isbn:
        return None
    url = "https://openlibrary.org/api/books"
    params = {
        "bibkeys": f"ISBN:{norm_isbn}",
        "format": "json",
        "jscmd": "data"
    }
    headers = {"User-Agent": "BookSearcher/1.0 (contact@example.com)"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        key = f"ISBN:{norm_isbn}"
        if key not in data:
            return None
        book_data = data[key]
        title = book_data.get("title", "Нет названия")
        authors = [a["name"] for a in book_data.get("authors", [])]
        if not authors:
            authors = ["Неизвестный автор"]

        year = None
        if "publish_date" in book_data:
            m = re.search(r'\d{4}', book_data["publish_date"])
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
            "year": year
        }
    except (RequestException, KeyError, ValueError):
        return None


def get_from_rsl(isbn: str) -> Optional[Dict[str, Any]]:
    """
    Синхронный поиск книги в Российской государственной библиотеке (РГБ) по ISBN.
    Парсит HTML-страницу результатов поиска.
    """
    url = "https://search.rsl.ru/ru/search"
    params = {"q": isbn}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        containers = soup.find_all('div', class_='search-container')
        if not containers:
            return None

        first = containers[0]

        author_tag = first.find('b', class_='js-item-authorinfo')
        authors = []
        if author_tag:
            authors = [author_tag.text.strip().rstrip('.')]
        else:
            authors = ["Неизвестный автор"]

        desc_span = first.find('span', class_='js-item-maininfo')
        if not desc_span:
            return None
        description = desc_span.text.strip()

        title = description.split(' / ')[0].strip()
        if not title:
            title = "Не удалось определить название"

        year = None
        year_match = re.search(r',\s*(\d{4})[\.\s\(]', description)
        if year_match:
            year = year_match.group(1)

        pages = None
        pages_match = re.search(r'\.\s*-\s*(\d+)\s+с\.', description)
        if pages_match:
            pages = pages_match.group(1)

        return {
            "title": title,
            "authors": authors,
            "source": "РГБ",
            "pages": pages or "не указано",
            "year": year or "не указан"
        }
    except Exception:
        return None