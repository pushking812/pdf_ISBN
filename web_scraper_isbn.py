import time
import re
from typing import Any, Dict, Optional, List
from bs4 import BeautifulSoup
from config import ScraperConfig
from utils import normalize_isbn
from resources import _book_ru_resource

def read_isbn_list(path: str = "isbn_list.txt") -> List[str]:
    """Читает список ISBN из файла, убирает пустые строки и дубликаты."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            seen = set()
            unique = []
            for line in f:
                isbn = line.strip()
                if isbn and isbn not in seen:
                    seen.add(isbn)
                    unique.append(isbn)
            return unique
    except FileNotFoundError:
        return [
            "978-5-907144-52-1",
            "978-0-13-417327-6",
            "978-5-04-089765-3",
            "978-5-699-93966-0"
        ]

def parse_book_page_for_resource(driver: Any, resource: Dict[str, Any]) -> Dict[str, Any]:
    """Упрощённый парсер страницы книги для тестов."""
    return {
        'title': '',
        'authors': [],
        'pages': '',
        'year': '',
        'url': driver.current_url,
        'source': resource.get('source_label', '')
    }

if __name__ == "__main__":
    # Импортируем функции поиска только в режиме запуска
    from scraper import search_multiple_books, print_results_table

    config = ScraperConfig(
        headless=False,
        skip_main_page=True,
        use_fast_selectors=True,
        wait_product_link=6,
        delay_after_main=(0.5, 1.0),
        delay_after_search=(0.8, 1.5),
        delay_after_click=(0.5, 1.0),
        poll_interval=0.5,
        no_product_phrases=["Похоже, у нас такого нет", "ничего не нашлось"],
        max_tabs=5,
        rate_limit_phrases=["DDoS-Guard", "DDOS", "Checking your browser", "Доступ ограничен"],
        rate_limit_initial_delay=10.0,
        rate_limit_coef_start=1.0,
        rate_limit_coef_step=0.2,
        rate_limit_coef_max=3.0,
        handle_rate_limit=True,
        keep_browser_open=False,
        verbose=True,
        api_max_concurrent=5
    )
    isbn_list = read_isbn_list()
    start = time.time()
    results = search_multiple_books(isbn_list, config)
    print(f"Общее время: {time.time() - start:.2f}с")
    print_results_table(isbn_list, results)