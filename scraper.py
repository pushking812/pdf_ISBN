"""
Обновленный модуль скрапинга, использующий новую архитектуру оркестратора.

Этот модуль заменяет старую реализацию скрапинга и использует:
1. Оркестратор из scraper_core.orchestrator.core
2. Конфигурационную систему из scraper_core.config
3. Функциональность debug_selectors через scraper_core.parsers
4. Совместимость с существующим кодом через scraper_core.orchestrator.legacy_adapter
"""

import asyncio
import time
import random
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

# Импорт новой архитектуры
from scraper_core.orchestrator.legacy_adapter import (
    TabState,
    TabInfo,
    async_parallel_search as new_async_parallel_search,
    process_isbn_async as new_process_isbn_async,
    run_api_stage as new_run_api_stage,
    search_multiple_books as new_search_multiple_books,
)
from scraper_core.integration.selector_integration import SelectorIntegration

# Импорт для обратной совместимости
from config import ScraperConfig


def parse_book_page_for_resource(
    driver: Any, resource: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Парсит страницу книги по селекторам указанного ресурса.

    ВНИМАНИЕ: Эта функция устарела и сохраняется только для обратной совместимости.
    В новой архитектуре используется функционал из scraper_core.parsers.selector_client.

    Args:
        driver: WebDriver Selenium
        resource: Конфигурация ресурса

    Returns:
        Словарь с данными книги
    """
    # Используем новую архитектуру через SelectorClient
    from scraper_core.parsers.selector_client import SelectorClient

    # Создаем клиент селекторов
    selector_client = SelectorClient({})

    # Получаем HTML страницы
    html = driver.page_source

    # Извлекаем данные с помощью нового функционала
    result = selector_client.extract_with_selectors(
        html=html,
        selectors=resource.get("selectors", []),
        resource_id=resource.get("id", "unknown"),
    )

    # Преобразуем результат в старый формат
    if result:
        return {
            "title": result.get("title", "Не удалось определить название"),
            "authors": result.get("authors", ["Неизвестный автор"]),
            "pages": result.get("pages", "не указано"),
            "year": result.get("year", "не указан"),
            "url": driver.current_url,
            "source": resource.get("source_label", "Сайт"),
            "isbn": result.get("isbn", ""),
            "confidence": result.get("confidence", 0.0),
        }

    # Если новый функционал не сработал, используем старую логику для совместимости
    custom_parser = resource.get("custom_parser")
    if custom_parser is not None:
        return custom_parser(driver, resource)

    soup = BeautifulSoup(driver.page_source, "lxml")
    # Проверка на страницу "ничего не найдено"
    no_product_phrases = resource.get("no_product_phrases", [])
    page_text = soup.get_text().lower()
    if any(phrase.lower() in page_text for phrase in no_product_phrases if phrase):
        return None

    title = None
    for sel in resource.get("title_selectors", []):
        elem = soup.select_one(sel)
        if elem:
            if getattr(elem, "name", "") == "meta":
                title = elem.get("content", "").strip()
            else:
                title = elem.get_text(strip=True)
            break

    if resource.get("id") == "book-ru" and title:
        title = title.split(" - ISBN")[0].strip()

    authors = []
    for sel in resource.get("author_selectors", []):
        elems = soup.select(sel)
        if elems:
            authors = [a.get_text(strip=True) for a in elems if a.get_text(strip=True)]
            if resource.get("id") == "book-ru" and authors:
                authors = [authors[0].split(",")[0].strip()]
            break

    pages = None
    for sel in resource.get("pages_selectors", []):
        elem = soup.select_one(sel)
        if elem:
            pages = elem.get_text(strip=True)
            break

    year = None
    for sel in resource.get("year_selectors", []):
        elem = soup.select_one(sel)
        if elem:
            year = elem.get_text(strip=True)
            break

    if resource.get("properties_item_class"):
        for li in soup.find_all("li", class_=resource["properties_item_class"]):
            title_elem = li.find(
                "span", class_=resource.get("properties_title_class", "")
            )
            content_elem = li.find(
                "span", class_=resource.get("properties_content_class", "")
            )
            if title_elem and content_elem:
                text = title_elem.get_text(strip=True)
                lower_text = text.lower()
                if not pages and (
                    "страниц" in lower_text
                    or "стр." in lower_text
                    or "объем" in lower_text
                ):
                    pages = content_elem.get_text(strip=True)
                if not year and "год" in lower_text:
                    year_span = content_elem.find("span", itemprop="copyrightYear")
                    if year_span and year_span.get_text(strip=True):
                        year = year_span.get_text(strip=True)
                    else:
                        year = content_elem.get_text(strip=True)

    if resource.get("id") == "book-ru" and pages:
        import re

        m = re.search(r"\d+", pages)
        if m:
            pages = m.group()

    return {
        "title": title or "Не удалось определить название",
        "authors": authors or ["Неизвестный автор"],
        "pages": pages or "не указано",
        "year": year or "не указан",
        "url": driver.current_url,
        "source": resource.get("source_label", "Сайт"),
    }


class RussianBookScraperUC:
    """
    Скрапер для Читай-города на основе Undetected ChromeDriver.

    ВНИМАНИЕ: Этот класс устарел и сохраняется только для обратной совместимости.
    В новой архитектуре используется ResourceHandler из scraper_core.handlers.
    """

    def __init__(self, config: Any):
        self.config = config
        self.driver = None
        self._init_selectors()

    def _init_selectors(self):
        if self.config.use_fast_selectors:
            self.product_link_selectors = ['a[href^="/product/"]']
            self.title_selectors = ["h1.product-detail-page__title", "h1.product-title"]
            self.author_selectors = [".product-authors a"]
            self.pages_selectors = ['span[itemprop="numberOfPages"] span']
            self.year_selectors = ['span[itemprop="datePublished"] span']
        else:
            self.product_link_selectors = [
                'a[href^="/product/"]',
                "a.product-card__title",
                "a.product-title",
                ".catalog-item a",
            ]
            self.title_selectors = [
                "h1.product-detail-page__title",
                "h1.product-title",
                'h1[itemprop="name"]',
                ".product__title h1",
                "h1",
            ]
            self.author_selectors = [
                ".product-authors a",
                ".product-author a",
                'a[itemprop="author"]',
                ".product-info__author",
                ".authors-list a",
            ]
            self.pages_selectors = [
                'span[itemprop="numberOfPages"] span',
                '.product-properties-item span[itemprop="numberOfPages"]',
            ]
            self.year_selectors = [
                'span[itemprop="datePublished"] span',
                '.product-properties-item span[itemprop="datePublished"]',
            ]
        self.properties_item_class = "product-properties-item"
        self.properties_title_class = "product-properties-item__title"
        self.properties_content_class = "product-properties-item__content"

    def __enter__(self):
        from drivers import create_chrome_driver

        self.driver = create_chrome_driver(self.config)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver and not self.config.keep_browser_open:
            self.driver.quit()

    def _random_delay(self, delay_range: Tuple[float, float], msg: str = ""):
        delay = random.uniform(*delay_range)
        if msg and self.config.verbose:
            print(f"⏱️ {msg}: {delay:.2f}с")
        time.sleep(delay)

    def _handle_city_modal(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            city_button = WebDriverWait(self.driver, self.config.wait_city_modal).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Да, я здесь')]")
                )
            )
            city_button.click()
            if self.config.verbose:
                print("🏙️ Город подтверждён")
            self._random_delay(self.config.delay_between_actions, "пауза после клика")
            return True
        except Exception:
            return False

    def _parse_book_page(self) -> Dict[str, Any]:
        soup = BeautifulSoup(self.driver.page_source, "lxml")
        title = None
        for sel in self.title_selectors:
            elem = soup.select_one(sel)
            if elem:
                title = elem.text.strip()
                break

        authors = []
        for sel in self.author_selectors:
            elems = soup.select(sel)
            if elems:
                authors = [a.text.strip() for a in elems if a.text.strip()]
                break

        pages = None
        for sel in self.pages_selectors:
            elem = soup.select_one(sel)
            if elem:
                pages = elem.text.strip()
                break

        year = None
        for sel in self.year_selectors:
            elem = soup.select_one(sel)
            if elem:
                year = elem.text.strip()
                break

        if not pages or not year:
            props = soup.find_all("li", class_=self.properties_item_class)
            for li in props:
                title_elem = li.find("span", class_=self.properties_title_class)
                if not title_elem:
                    continue
                text = title_elem.text.strip()
                content_elem = li.find("span", class_=self.properties_content_class)
                if not content_elem:
                    continue
                if "Количество страниц" in text and not pages:
                    pages = content_elem.text.strip()
                elif "Год издания" in text and not year:
                    year = content_elem.text.strip()

        return {
            "title": title or "Не удалось определить название",
            "authors": authors or ["Неизвестный автор"],
            "pages": pages or "не указано",
            "year": year or "не указан",
            "url": self.driver.current_url,
            "source": "Читай-город",
        }

    def search_by_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        """Поиск по одному ISBN (синхронный, для одной вкладки)."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException

        clean_isbn = isbn.replace("-", "").strip()
        search_url = f"{self.config.base_url}/search?phrase={clean_isbn}"
        try:
            if not self.config.skip_main_page:
                self.driver.get(self.config.base_url)
                self._random_delay(self.config.delay_after_main, "после главной")
                self._handle_city_modal()
            else:
                if self.config.verbose:
                    print("⏩ Пропускаем главную страницу (skip_main_page=True)")

            self.driver.get(search_url)
            self._random_delay(self.config.delay_after_search, "после поиска")
            self._handle_city_modal()

            product_link = None
            for selector in self.product_link_selectors:
                try:
                    product_link = WebDriverWait(
                        self.driver, self.config.wait_product_link
                    ).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    break
                except TimeoutException:
                    continue

            if not product_link:
                if self.config.verbose:
                    print("❌ Ссылка на книгу не найдена.")
                return None

            book_url = product_link.get_attribute("href")
            self.driver.get(book_url)
            self._random_delay(self.config.delay_after_click, "после перехода на книгу")
            return self._parse_book_page()
        except Exception:
            return None


# Основные функции скрапинга - теперь используют новую архитектуру
async def async_parallel_search(
    isbn_list: List[str], config: Optional[ScraperConfig] = None
) -> List[Optional[Dict[str, Any]]]:
    """
    Асинхронный параллельный поиск по списку ISBN.

    Эта функция теперь использует новую архитектуру оркестратора.

    Args:
        isbn_list: Список ISBN для поиска
        config: Конфигурация скрапера (опционально)

    Returns:
        Список результатов для каждого ISBN
    """
    return await new_async_parallel_search(isbn_list, config)


async def process_isbn_async(
    raw_isbn: str,
    config: Optional[ScraperConfig] = None,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> Optional[Dict[str, Any]]:
    """
    Обработка одного ISBN (асинхронно).

    Эта функция теперь использует новую архитектуру оркестратора.

    Args:
        raw_isbn: ISBN для обработки
        config: Конфигурация скрапера (опционально)
        semaphore: Семафор для ограничения параллелизма (опционально)

    Returns:
        Результат скрапинга или None
    """
    return await new_process_isbn_async(raw_isbn, config, semaphore)


async def run_api_stage(
    isbn_list: List[str],
    config: Optional[ScraperConfig] = None,
    connector: Optional[Any] = None,
) -> List[Optional[Dict[str, Any]]]:
    """
    Запуск API-стадии (Google Books, Open Library).

    Эта функция теперь использует новую архитектуру оркестратора.

    Args:
        isbn_list: Список ISBN для поиска через API
        config: Конфигурация скрапера (опционально)
        connector: Коннектор aiohttp (опционально)

    Returns:
        Список результатов API
    """
    return await new_run_api_stage(isbn_list, config, connector)


def search_multiple_books(
    isbn_list: List[str], config: Optional[ScraperConfig] = None
) -> List[Optional[Dict[str, Any]]]:
    """
    Синхронный поиск по нескольким ISBN.

    Эта функция теперь использует новую архитектуру оркестратора.

    Args:
        isbn_list: Список ISBN для поиска
        config: Конфигурация скрапера (опционально)

    Returns:
        Список результатов
    """
    return new_search_multiple_books(isbn_list, config)


# Функции для миграции и обновления конфигурации
def migrate_to_new_architecture(config_dir: str = "config") -> Dict[str, int]:
    """
    Миграция существующих данных в новую архитектуру.

    Args:
        config_dir: Директория с конфигурационными файлами

    Returns:
        Словарь с результатами миграции
    """
    selector_integration = SelectorIntegration(config_dir)
    return selector_integration.migrate_existing_selectors()


def update_selectors_from_results(config_dir: str = "config") -> Dict[str, List[Dict]]:
    """
    Обновление селекторов на основе результатов скрапинга.

    Args:
        config_dir: Директория с конфигурационными файлами

    Returns:
        Словарь с обновленными селекторами по ресурсам
    """
    selector_integration = SelectorIntegration(config_dir)
    return selector_integration.auto_generate_all_selectors()


# Экспорт для обратной совместимости
__all__ = [
    "parse_book_page_for_resource",
    "TabState",
    "TabInfo",
    "RussianBookScraperUC",
    "async_parallel_search",
    "process_isbn_async",
    "run_api_stage",
    "search_multiple_books",
    "migrate_to_new_architecture",
    "update_selectors_from_results",
]
