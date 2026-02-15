import time
import random
import asyncio
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from drivers import create_chrome_driver
from resources import get_scraper_resources
from api_clients import (
    get_from_google_books_async,
    get_from_open_library_async,
    get_from_rsl_async,
    get_from_google_books,
    get_from_open_library,
    get_from_rsl
)
from config import ScraperConfig
from utils import normalize_isbn

def parse_book_page_for_resource(driver: Any, resource: Dict[str, Any]) -> Dict[str, Any]:
    """Парсит страницу книги по селекторам указанного ресурса."""
    soup = BeautifulSoup(driver.page_source, 'lxml')
    title = None
    for sel in resource.get("title_selectors", []):
        elem = soup.select_one(sel)
        if elem:
            if getattr(elem, 'name', '') == 'meta':
                title = elem.get('content', '').strip()
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
        for li in soup.find_all('li', class_=resource["properties_item_class"]):
            title_elem = li.find('span', class_=resource.get("properties_title_class", ""))
            content_elem = li.find('span', class_=resource.get("properties_content_class", ""))
            if title_elem and content_elem:
                text = title_elem.get_text(strip=True)
                lower_text = text.lower()
                if not pages and ('страниц' in lower_text or 'стр.' in lower_text or 'объем' in lower_text):
                    pages = content_elem.get_text(strip=True)
                if not year and 'год' in lower_text:
                    year_span = content_elem.find('span', itemprop="copyrightYear")
                    if year_span and year_span.get_text(strip=True):
                        year = year_span.get_text(strip=True)
                    else:
                        year = content_elem.get_text(strip=True)
    if resource.get("id") == "book-ru" and pages:
        import re
        m = re.search(r'\d+', pages)
        if m:
            pages = m.group()
    return {
        'title': title or "Не удалось определить название",
        'authors': authors or ["Неизвестный автор"],
        'pages': pages or "не указано",
        'year': year or "не указан",
        'url': driver.current_url,
        'source': resource.get("source_label", "Сайт"),
    }

class TabState(Enum):
    INIT = 0
    SEARCHING = 1
    BOOK_PAGE = 2
    DONE = 3
    ERROR = 4
    RATE_LIMITED = 5

class TabInfo:
    def __init__(self, isbn: str, handle: str, index: int, config: Any):
        self.isbn = isbn
        self.handle = handle
        self.index = index
        self.state = TabState.INIT
        self.result = None
        self.error = None
        self.book_url = None
        self.search_start_time = None
        self.timeout = config.wait_product_link
        self.start_resource_index = 0
        self.tried_resources = 0

class RussianBookScraperUC:
    """Скрапер для Читай-города на основе Undetected ChromeDriver."""
    def __init__(self, config: Any):
        self.config = config
        self.driver = None
        self._init_selectors()

    def _init_selectors(self):
        if self.config.use_fast_selectors:
            self.product_link_selectors = ['a[href^="/product/"]']
            self.title_selectors = ['h1.product-detail-page__title', 'h1.product-title']
            self.author_selectors = ['.product-authors a']
            self.pages_selectors = ['span[itemprop="numberOfPages"] span']
            self.year_selectors = ['span[itemprop="datePublished"] span']
        else:
            self.product_link_selectors = [
                'a[href^="/product/"]',
                'a.product-card__title',
                'a.product-title',
                '.catalog-item a'
            ]
            self.title_selectors = [
                'h1.product-detail-page__title',
                'h1.product-title',
                'h1[itemprop="name"]',
                '.product__title h1',
                'h1'
            ]
            self.author_selectors = [
                '.product-authors a',
                '.product-author a',
                'a[itemprop="author"]',
                '.product-info__author',
                '.authors-list a'
            ]
            self.pages_selectors = [
                'span[itemprop="numberOfPages"] span',
                '.product-properties-item span[itemprop="numberOfPages"]'
            ]
            self.year_selectors = [
                'span[itemprop="datePublished"] span',
                '.product-properties-item span[itemprop="datePublished"]'
            ]
        self.properties_item_class = 'product-properties-item'
        self.properties_title_class = 'product-properties-item__title'
        self.properties_content_class = 'product-properties-item__content'

    def __enter__(self):
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
        try:
            city_button = WebDriverWait(self.driver, self.config.wait_city_modal).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Да, я здесь')]"))
            )
            city_button.click()
            if self.config.verbose:
                print("🏙️ Город подтверждён")
            self._random_delay(self.config.delay_between_actions, "пауза после клика")
            return True
        except:
            return False

    def _parse_book_page(self) -> Dict[str, Any]:
        soup = BeautifulSoup(self.driver.page_source, 'lxml')
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
            props = soup.find_all('li', class_=self.properties_item_class)
            for li in props:
                title_elem = li.find('span', class_=self.properties_title_class)
                if not title_elem:
                    continue
                text = title_elem.text.strip()
                content_elem = li.find('span', class_=self.properties_content_class)
                if not content_elem:
                    continue
                if 'Количество страниц' in text and not pages:
                    pages = content_elem.text.strip()
                elif 'Год издания' in text and not year:
                    year = content_elem.text.strip()
        return {
            'title': title or "Не удалось определить название",
            'authors': authors or ["Неизвестный автор"],
            'pages': pages or "не указано",
            'year': year or "не указан",
            'url': self.driver.current_url,
            'source': 'Читай-город'
        }

    def search_by_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        """Поиск по одному ISBN (синхронный, для одной вкладки)."""
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
                    product_link = WebDriverWait(self.driver, self.config.wait_product_link).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except TimeoutException:
                    continue
            if not product_link:
                if self.config.verbose:
                    print("❌ Ссылка на книгу не найдена.")
                return None
            book_url = product_link.get_attribute('href')
            self.driver.get(book_url)
            self._random_delay(self.config.delay_after_click, "после перехода на книгу")
            return self._parse_book_page()
        except Exception:
            return None

async def async_parallel_search(isbn_list: List[str], config: Optional[ScraperConfig] = None) -> List[Optional[Dict[str, Any]]]:
    if config is None:
        from config import ScraperConfig
        config = ScraperConfig()
    resources = get_scraper_resources(config)
    driver = create_chrome_driver(config)
    delay_tab = getattr(config, 'delay_tab_switch', 0.2)
    chunks = [isbn_list[i:i + config.max_tabs] for i in range(0, len(isbn_list), config.max_tabs)]
    all_results: List[Optional[Dict[str, Any]]] = []
    rate_limit_attempts = 0
    for chunk_idx, chunk in enumerate(chunks):
        main_handle = driver.current_window_handle
        handles = [main_handle]
        for _ in chunk[1:]:
            driver.switch_to.new_window('tab')
            time.sleep(delay_tab)
            handles.append(driver.current_window_handle)
        tabs = [TabInfo(chunk[i], handles[i], i, config) for i in range(len(chunk))]
        for i, tab in enumerate(tabs):
            tab.start_resource_index = (chunk_idx * config.max_tabs + i) % len(resources)
        def _load_search_for_tab(tab: TabInfo, resource: Dict[str, Any]):
            clean = tab.isbn.replace("-", "").strip()
            url = resource["search_url_template"].format(isbn=clean)
            if resource.get("need_main_page") and tab.handle == main_handle:
                driver.get(resource["base_url"])
                time.sleep(random.uniform(*config.delay_after_main))
            driver.get(url)
            tab.search_start_time = time.time()
            tab.state = TabState.SEARCHING
        for tab in tabs:
            driver.switch_to.window(tab.handle)
            _load_search_for_tab(tab, resources[(tab.start_resource_index + tab.tried_resources) % len(resources)])
            time.sleep(delay_tab)
        all_done = False
        while not all_done:
            all_done = True
            for tab in tabs:
                if tab.state in (TabState.DONE, TabState.ERROR):
                    continue
                all_done = False
                driver.switch_to.window(tab.handle)
                res = resources[(tab.start_resource_index + tab.tried_resources) % len(resources)]
                try:
                    if any(phrase.lower() in driver.page_source.lower() for phrase in config.rate_limit_phrases):
                        time.sleep(config.rate_limit_initial_delay)
                        driver.refresh()
                        continue
                    if tab.state == TabState.SEARCHING:
                        for selector in res.get("product_link_selectors", []):
                            try:
                                elem = driver.find_element(By.CSS_SELECTOR, selector)
                                href = elem.get_attribute('href')
                                if href:
                                    tab.book_url = href
                                    driver.get(href)
                                    time.sleep(random.uniform(*config.delay_after_click))
                                    tab.state = TabState.BOOK_PAGE
                                    break
                            except NoSuchElementException:
                                continue
                        else:
                            if time.time() - tab.search_start_time > tab.timeout:
                                tab.tried_resources += 1
                                if tab.tried_resources >= len(resources):
                                    tab.state = TabState.ERROR
                                else:
                                    _load_search_for_tab(tab, resources[(tab.start_resource_index + tab.tried_resources) % len(resources)])
                    elif tab.state == TabState.BOOK_PAGE:
                        tab.result = parse_book_page_for_resource(driver, res)
                        tab.state = TabState.DONE
                except Exception:
                    tab.state = TabState.ERROR
            if not all_done:
                await asyncio.sleep(config.poll_interval)
        for h in handles[1:]:
            driver.switch_to.window(h)
            driver.close()
        driver.switch_to.window(handles[0])
        all_results.extend([tab.result for tab in tabs])
    driver.quit()
    return all_results

async def process_isbn_async(
    session: aiohttp.ClientSession,
    raw_isbn: str,
    idx: int,
    config: ScraperConfig,
    semaphore: asyncio.Semaphore,
) -> Tuple[int, Optional[Dict[str, Any]]]:
    norm_isbn = normalize_isbn(raw_isbn)
    if not norm_isbn:
        return idx, None
    async with semaphore:
        tasks = [
            get_from_google_books_async(session, norm_isbn),
            get_from_open_library_async(session, norm_isbn),
            get_from_rsl_async(session, raw_isbn)
        ]
        results = await asyncio.gather(*tasks)
    for res in results:
        if res:
            return idx, res
    return idx, None

async def run_api_stage(isbn_list: List[str], config: Optional[ScraperConfig] = None) -> Tuple[List[Optional[Dict[str, Any]]], List[str], List[int]]:
    if config is None:
        from config import ScraperConfig
        config = ScraperConfig()
    results: List[Optional[Dict[str, Any]]] = [None] * len(isbn_list)
    remaining_isbns: List[str] = []
    remaining_indices: List[int] = []
    connector = aiohttp.TCPConnector(limit_per_host=config.api_max_concurrent * 2)
    semaphore = asyncio.Semaphore(config.api_max_concurrent)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [process_isbn_async(session, isbn_list[i], i, config, semaphore) for i in range(len(isbn_list))]
        for future in asyncio.as_completed(tasks):
            idx, res = await future
            if res:
                results[idx] = res
            else:
                remaining_isbns.append(isbn_list[idx])
                remaining_indices.append(idx)
    return results, remaining_isbns, remaining_indices

def search_book_by_isbn(isbn: str, config: Optional[ScraperConfig] = None) -> Optional[Dict[str, Any]]:
    from config import ScraperConfig
    if config is None:
        config = ScraperConfig()
    norm_isbn = normalize_isbn(isbn)
    if not norm_isbn:
        print(f"⚠️ Некорректный ISBN: {isbn}")
        return None
    res = get_from_google_books(norm_isbn)
    if res:
        return res
    res = get_from_open_library(norm_isbn)
    if res:
        return res
    res = get_from_rsl(isbn)
    if res:
        return res
    with RussianBookScraperUC(config) as scraper:
        return scraper.search_by_isbn(isbn)

def search_multiple_books(isbn_list: List[str], config: Optional[ScraperConfig] = None) -> List[Optional[Dict[str, Any]]]:
    from config import ScraperConfig
    if config is None:
        config = ScraperConfig()
    results, remaining, indices = asyncio.run(run_api_stage(isbn_list, config))
    if remaining:
        scraped = asyncio.run(async_parallel_search(remaining, config))
        for i, res in zip(indices, scraped):
            results[i] = res
    return results