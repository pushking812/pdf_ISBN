import pytest
import pytest_asyncio
import aiohttp
from pathlib import Path
from config import ScraperConfig


def load_isbn_list() -> list[str]:
    """Загружает список ISBN из файла isbn_list.txt."""
    path = Path(__file__).parent.parent / "isbn_list.txt"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    isbns = [line.strip() for line in lines if line.strip()]
    return isbns


@pytest.fixture(scope="session")
def isbn_list() -> list[str]:
    """Фикстура, возвращающая список ISBN."""
    return load_isbn_list()


@pytest_asyncio.fixture(scope="session")
async def aiohttp_session():
    """Сессия aiohttp для асинхронных тестов."""
    session = aiohttp.ClientSession()
    yield session
    await session.close()


@pytest.fixture(scope="session")
def scraper_config() -> ScraperConfig:
    """Конфигурация скрапера по умолчанию."""
    return ScraperConfig(headless=True, skip_main_page=True)
