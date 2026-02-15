import aiohttp
from typing import Any, Optional, Dict
import requests
from bs4 import BeautifulSoup
import re

async def get_from_google_books_async(session: aiohttp.ClientSession, isbn: str) -> Optional[Dict[str, Any]]:
    """Stub async Google Books клиент."""
    return None

async def get_from_open_library_async(session: aiohttp.ClientSession, isbn: str) -> Optional[Dict[str, Any]]:
    """Stub async Open Library клиент."""
    return None

async def get_from_rsl_async(session: aiohttp.ClientSession, isbn: str) -> Optional[Dict[str, Any]]:
    """Stub async РГБ клиент."""
    return None

def get_from_google_books(isbn: str) -> Optional[Dict[str, Any]]:
    """Stub sync Google Books клиент."""
    return None

def get_from_open_library(isbn: str) -> Optional[Dict[str, Any]]:
    """Stub sync Open Library клиент."""
    return None

def get_from_rsl(isbn: str) -> Optional[Dict[str, Any]]:
    """Stub sync РГБ клиент."""
    return None