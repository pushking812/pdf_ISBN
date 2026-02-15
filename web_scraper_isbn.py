import asyncio
import aiohttp
import re
import time
import random
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum
import requests
from requests.exceptions import RequestException
import isbnlib

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, InvalidSessionIdException, WebDriverException
from bs4 import BeautifulSoup


# ==================== КОНФИГУРАЦИЯ ====================
class ScraperConfig:
    """Конфигурация скрапера."""
    def __init__(self,
                 headless: bool = False,
                 base_url: str = "https://www.chitai-gorod.ru",
                 skip_main_page: bool = False,
                 use_fast_selectors: bool = False,
                 # Фиксированные задержки
                 delay_after_main: Tuple[float, float] = (1.5, 2.5),
                 delay_after_search: Tuple[float, float] = (2.0, 3.0),
                 delay_after_click: Tuple[float, float] = (1.5, 2.5),
                 delay_between_actions: Tuple[float, float] = (0.3, 0.7),
                 wait_city_modal: int = 3,
                 wait_product_link: int = 6,
                 # Параметры асинхронного цикла
                 poll_interval: float = 0.5,
                 # Фразы, указывающие на отсутствие товара в результатах поиска
                 no_product_phrases: List[str] = None,
                 # Максимальное количество одновременно открытых вкладок
                 max_tabs: int = 5,
                 # Фразы, указывающие на блокировку (Too many requests)
                 rate_limit_phrases: List[str] = None,
                 # Начальная задержка при обнаружении блокировки (сек)
                 rate_limit_initial_delay: float = 10.0,
                 # Начальный коэффициент множителя
                 rate_limit_coef_start: float = 1.0,
                 # Шаг увеличения коэффициента
                 rate_limit_coef_step: float = 0.2,
                 # Максимальный коэффициент множителя
                 rate_limit_coef_max: float = 3.0,
                 # Обрабатывать ли блокировку (если False, то игнорируется)
                 handle_rate_limit: bool = True,
                # Оставить браузер открытым после завершения (для отладки)
                keep_browser_open: bool = False,
                # Подробное логирование
                verbose: bool = False,
                # Макс. кол-во одновременно обрабатываемых ISBN на этапе API/РГБ (снижает блокировки РГБ/API)
                api_max_concurrent: int = 5):
        self.headless = headless
        self.base_url = base_url
        self.skip_main_page = skip_main_page
        self.use_fast_selectors = use_fast_selectors
        self.delay_after_main = delay_after_main
        self.delay_after_search = delay_after_search
        self.delay_after_click = delay_after_click
        self.delay_between_actions = delay_between_actions
        self.wait_city_modal = wait_city_modal
        self.wait_product_link = wait_product_link
        self.poll_interval = poll_interval
        self.no_product_phrases = no_product_phrases or [
            "Похоже, у нас такого нет",
            "ничего не нашлось"
        ]
        self.max_tabs = max_tabs
        self.rate_limit_phrases = rate_limit_phrases or [
            "DDoS-Guard",
            "DDOS",
            "Checking your browser",
            "Доступ ограничен"
        ]
        self.rate_limit_initial_delay = rate_limit_initial_delay
        self.rate_limit_coef_start = rate_limit_coef_start
        self.rate_limit_coef_step = rate_limit_coef_step
        self.rate_limit_coef_max = rate_limit_coef_max
        self.handle_rate_limit = handle_rate_limit
        self.keep_browser_open = keep_browser_open
        self.verbose = verbose
        self.api_max_concurrent = api_max_concurrent


# ==================== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ISBN ====================
def normalize_isbn(isbn: str) -> Optional[str]:
    """
    Принимает ISBN (10 или 13 знаков, с дефисами или без),
    возвращает канонический 13-значный код (без дефисов) или None, если код невалиден.
    """
    clean = isbnlib.canonical(isbn)
    if not clean:
        return None
    if isbnlib.is_isbn13(clean):
        return clean
    if isbnlib.is_isbn10(clean):
        return isbnlib.to_isbn13(clean)
    return None


# ==================== АСИНХРОННЫЕ API ФУНКЦИИ ====================
async def get_from_google_books_async(session: aiohttp.ClientSession, isbn: str) -> Optional[Dict[str, Any]]:
    """Асинхронный поиск книги в Google Books API по ISBN."""
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": f"isbn:{isbn}", "maxResults": 1}
    try:
        async with session.get(url, params=params, timeout=10) as response:
            if response.status != 200:
                return None
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
    except Exception:
        return None


async def get_from_open_library_async(session: aiohttp.ClientSession, isbn: str) -> Optional[Dict[str, Any]]:
    """Асинхронный поиск книги в Open Library API по ISBN."""
    url = "https://openlibrary.org/api/books"
    params = {
        "bibkeys": f"ISBN:{isbn}",
        "format": "json",
        "jscmd": "data"
    }
    headers = {"User-Agent": "BookSearcher/1.0 (contact@example.com)"}
    try:
        async with session.get(url, params=params, headers=headers, timeout=10) as response:
            if response.status != 200:
                return None
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
    except Exception:
        return None


async def get_from_rsl_async(session: aiohttp.ClientSession, isbn: str) -> Optional[Dict[str, Any]]:
    """
    Асинхронный поиск книги в Российской государственной библиотеке (РГБ) по ISBN.
    """
    url = "https://search.rsl.ru/ru/search"
    params = {"q": isbn}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with session.get(url, params=params, headers=headers, timeout=15) as response:
            if response.status != 200:
                return None
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
            year_match = re.search(r',\s*(\d{4})\.', description)
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


# ==================== СИНХРОННЫЕ ОБЁРТКИ ДЛЯ СОВМЕСТИМОСТИ (МОЖНО ОСТАВИТЬ) ====================
# (Не используются в новой версии, но оставлены для возможного вызова)

def get_from_google_books(isbn: str) -> Optional[Dict[str, Any]]:
    # Синхронная версия (для совместимости)
    import requests
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": f"isbn:{isbn}", "maxResults": 1}
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
    except Exception:
        return None


def get_from_open_library(isbn: str) -> Optional[Dict[str, Any]]:
    # Синхронная версия
    import requests
    url = "https://openlibrary.org/api/books"
    params = {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"}
    headers = {"User-Agent": "BookSearcher/1.0 (contact@example.com)"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
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
    except Exception:
        return None


def get_from_rsl(isbn: str) -> Optional[Dict[str, Any]]:
    # Синхронная версия
    import requests
    from bs4 import BeautifulSoup
    url = "https://search.rsl.ru/ru/search"
    params = {"q": isbn}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        containers = soup.find_all('div', class_='search-container')
        if not containers:
            return None
        first = containers[0]
        author_tag = first.find('b', class_='js-item-authorinfo')
        authors = [author_tag.text.strip().rstrip('.')] if author_tag else ["Неизвестный автор"]
        desc_span = first.find('span', class_='js-item-maininfo')
        if not desc_span:
            return None
        description = desc_span.text.strip()
        title = description.split(' / ')[0].strip() or "Не удалось определить название"
        year = None
        year_match = re.search(r',\s*(\d{4})\.', description)
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


# ==================== ОСНОВНОЙ КЛАСС СКРАПЕРА ====================
class TabState(Enum):
    INIT = 0
    SEARCHING = 1
    BOOK_PAGE = 2
    DONE = 3
    ERROR = 4
    RATE_LIMITED = 5


class TabInfo:
    def __init__(self, isbn: str, handle: str, index: int, config: ScraperConfig):
        self.isbn = isbn
        self.handle = handle
        self.index = index
        self.state = TabState.INIT
        self.result = None
        self.error = None
        self.book_url = None
        self.search_start_time = None
        self.timeout = config.wait_product_link


class RussianBookScraperUC:
    """Скрапер для Читай-города на основе Undetected ChromeDriver."""
    def __init__(self, config: ScraperConfig):
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
        self.driver = uc.Chrome(headless=self.config.headless)
        self.driver.set_window_size(1920, 1080)
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
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

        title = title or "Не удалось определить название"
        authors = authors or ["Неизвестный автор"]
        pages = pages or "не указано"
        year = year or "не указан"

        return {
            'title': title,
            'authors': authors,
            'pages': pages,
            'year': year,
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

        except Exception as e:
            if self.config.verbose:
                print(f"❌ Ошибка: {e}")
            return None


# ==================== ПАРАЛЛЕЛЬНЫЙ ПОИСК (ЧАНКОВЫЙ АЛГОРИТМ ИЗ scrapper14) ====================
def async_parallel_search(isbn_list: List[str], config: Optional[ScraperConfig] = None) -> List[Optional[Dict[str, Any]]]:
    """
    Асинхронный поиск нескольких ISBN в одном браузере с разбиением на чанки.
    Проверенная быстрая реализация из scrapper14.
    """
    if config is None:
        config = ScraperConfig()

    # Создаём драйвер (вне контекстного менеджера, чтобы управлять вручную)
    driver = uc.Chrome(headless=config.headless)
    driver.set_window_size(1920, 1080)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Обработка главной страницы, если нужно
    if not config.skip_main_page:
        driver.get(config.base_url)
        time.sleep(random.uniform(*config.delay_after_main))
        try:
            WebDriverWait(driver, config.wait_city_modal).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Да, я здесь')]"))
            ).click()
            if config.verbose:
                print("🏙️ Город подтверждён (главное окно)")
            time.sleep(random.uniform(*config.delay_between_actions))
        except:
            pass
    else:
        if config.verbose:
            print("⏩ Пропускаем главную страницу")

    # Разбиваем список ISBN на чанки по max_tabs
    chunks = [isbn_list[i:i + config.max_tabs] for i in range(0, len(isbn_list), config.max_tabs)]
    all_results = []
    rate_limit_attempts = 0

    # Создаём временный объект scraper для доступа к селекторам
    scraper_template = RussianBookScraperUC(config)

    for chunk_idx, chunk in enumerate(chunks):
        if config.verbose:
            print(f"\n=== Обработка чанка {chunk_idx + 1}/{len(chunks)} (ISBN: {chunk}) ===")

        # Создание вкладок для текущего чанка
        handles = []
        try:
            main_handle = driver.current_window_handle
            handles.append(main_handle)
            for i in range(1, len(chunk)):
                driver.switch_to.new_window('tab')
                time.sleep(0.5)
                new_handle = driver.current_window_handle
                if new_handle not in handles:
                    handles.append(new_handle)
                else:
                    all_handles = driver.window_handles
                    found = False
                    for h in all_handles:
                        if h not in handles:
                            handles.append(h)
                            found = True
                            break
                    if not found:
                        raise Exception(f"Не удалось получить новый handle для вкладки {i}")
        except Exception as e:
            if config.verbose:
                print(f"❌ Ошибка создания вкладок: {e}")
            all_results.extend([None] * len(chunk))
            time.sleep(1)
            continue

        tabs = [TabInfo(chunk[i], handles[i], i, config) for i in range(len(chunk))]

        # Загрузка поисковых страниц в каждую вкладку
        for tab in tabs:
            try:
                driver.switch_to.window(tab.handle)
                clean_isbn = tab.isbn.replace("-", "").strip()
                search_url = f"{config.base_url}/search?phrase={clean_isbn}"
                driver.get(search_url)
                tab.state = TabState.SEARCHING
                tab.search_start_time = time.time()
                time.sleep(0.2)
            except Exception as e:
                if config.verbose:
                    print(f"❌ [Вкладка {tab.index}] Не удалось загрузить поиск: {e}")
                tab.state = TabState.ERROR

        # Основной цикл обработки чанка
        all_done = False
        while not all_done:
            all_done = True
            for tab in tabs:
                if tab.state in (TabState.DONE, TabState.ERROR, TabState.RATE_LIMITED):
                    continue
                all_done = False

                try:
                    driver.switch_to.window(tab.handle)
                except Exception as e:
                    if config.verbose:
                        print(f"❌ [Вкладка {tab.index}] Ошибка переключения: {e}")
                    tab.state = TabState.ERROR
                    continue

                # Проверка блокировки
                if config.handle_rate_limit:
                    try:
                        page_source = driver.page_source
                        found_rate_limit = any(phrase.lower() in page_source.lower() for phrase in config.rate_limit_phrases)
                        if found_rate_limit:
                            if config.verbose:
                                print(f"⚠️ [Вкладка {tab.index}] Обнаружена блокировка")
                            rate_limit_attempts += 1
                            coef = config.rate_limit_coef_start + (rate_limit_attempts - 1) * config.rate_limit_coef_step
                            coef = min(coef, config.rate_limit_coef_max)
                            wait_time = config.rate_limit_initial_delay * coef
                            if config.verbose:
                                print(f"⏸️ Пауза {wait_time:.1f}с (коэф. {coef:.2f})")
                            time.sleep(wait_time)
                            driver.refresh()
                            while True:
                                time.sleep(config.poll_interval)
                                page_source = driver.page_source
                                if any(phrase.lower() in page_source.lower() for phrase in config.rate_limit_phrases):
                                    time.sleep(wait_time)
                                    driver.refresh()
                                else:
                                    if config.verbose:
                                        print(f"↻ Блокировка снята, сброс счётчика")
                                    rate_limit_attempts = 0
                                    break
                            for t in tabs:
                                if t.handle != tab.handle:
                                    try:
                                        driver.switch_to.window(t.handle)
                                        driver.refresh()
                                        time.sleep(0.5)
                                    except:
                                        pass
                            driver.switch_to.window(tab.handle)
                            break
                        else:
                            if rate_limit_attempts > 0:
                                rate_limit_attempts = 0
                    except Exception:
                        pass

                if tab.state == TabState.SEARCHING:
                    try:
                        page_source = driver.page_source
                        if any(phrase in page_source for phrase in config.no_product_phrases):
                            if config.verbose:
                                print(f"❌ [Вкладка {tab.index}] Товар не найден")
                            tab.state = TabState.ERROR
                            continue
                    except:
                        pass

                    elapsed = time.time() - tab.search_start_time
                    found_link = None
                    for selector in scraper_template.product_link_selectors:
                        try:
                            element = driver.find_element(By.CSS_SELECTOR, selector)
                            found_link = element
                            break
                        except NoSuchElementException:
                            continue
                    if found_link:
                        tab.book_url = found_link.get_attribute('href')
                        driver.get(tab.book_url)
                        time.sleep(random.uniform(*config.delay_after_click))
                        tab.state = TabState.BOOK_PAGE
                        if config.verbose:
                            print(f"📖 [Вкладка {tab.index}] Перешли на страницу книги")
                    else:
                        if elapsed > tab.timeout:
                            if config.verbose:
                                print(f"❌ [Вкладка {tab.index}] Превышен таймаут")
                            tab.state = TabState.ERROR

                elif tab.state == TabState.BOOK_PAGE:
                    try:
                        scraper_template.driver = driver
                        result = scraper_template._parse_book_page()
                        tab.result = result
                        tab.state = TabState.DONE
                        rate_limit_attempts = 0
                        if config.verbose:
                            print(f"\n✅ [Вкладка {tab.index}] ISBN {tab.isbn} готов")
                    except Exception as e:
                        if config.verbose:
                            print(f"❌ [Вкладка {tab.index}] Ошибка парсинга: {e}")
                        tab.state = TabState.ERROR

            if not all_done:
                time.sleep(config.poll_interval)

        # Закрытие вкладок чанка (кроме главной)
        main_handle = handles[0]
        for handle in handles[1:]:
            try:
                driver.switch_to.window(handle)
                driver.close()
            except:
                pass
        driver.switch_to.window(main_handle)
        all_results.extend([tab.result for tab in tabs])
        time.sleep(1)

    if not config.keep_browser_open:
        driver.quit()
    else:
        input("\n🔍 Браузер оставлен открытым. Нажмите Enter для закрытия...")
        driver.quit()

    return all_results


# ==================== АСИНХРОННАЯ ОБРАБОТКА ЭТАПА API/РГБ ====================
async def process_isbn_async(
    session: aiohttp.ClientSession,
    raw_isbn: str,
    idx: int,
    config: ScraperConfig,
    semaphore: asyncio.Semaphore,
) -> Tuple[int, Optional[Dict[str, Any]]]:
    """
    Асинхронно обрабатывает один ISBN: запускает параллельные запросы ко всем трём источникам
    и возвращает первый успешный результат или None.
    Семафор ограничивает число одновременно обрабатываемых ISBN, чтобы не перегружать РГБ/API.
    """
    norm_isbn = normalize_isbn(raw_isbn)
    if not norm_isbn:
        return idx, None

    async with semaphore:
        tasks = [
            get_from_google_books_async(session, norm_isbn),
            get_from_open_library_async(session, norm_isbn),
            get_from_rsl_async(session, raw_isbn)   # РГБ использует исходный ISBN
        ]
        results = await asyncio.gather(*tasks)

    for res in results:
        if res:
            return idx, res
    return idx, None


async def run_api_stage(isbn_list: List[str], config: ScraperConfig) -> Tuple[List[Optional[Dict[str, Any]]], List[str], List[int]]:
    """
    Асинхронно выполняет этап API/РГБ для всего списка ISBN.
    Возвращает:
      - results: список результатов (размер равен len(isbn_list), None если не найдено)
      - remaining_isbns: список ISBN, не найденных на этом этапе
      - remaining_indices: соответствующие индексы
    """
    results = [None] * len(isbn_list)
    remaining_isbns = []
    remaining_indices = []

    total = len(isbn_list)
    print("\n🔍 Поиск через API и РГБ (параллельно):")
    header = f"{' №':>4} | {'ISBN':<20} | {'Google Books':<12} | {'Open Library':<12} | {'РГБ':<8} | Статус"
    print(header)
    print("-" * len(header))

    semaphore = asyncio.Semaphore(config.api_max_concurrent)
    # Ограничиваем соединения на хост, чтобы РГБ/API не блокировали при всплесках запросов
    connector = aiohttp.TCPConnector(limit_per_host=config.api_max_concurrent * 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [process_isbn_async(session, isbn_list[i], i, config, semaphore) for i in range(total)]
        # Запускаем задачи с ограничением параллелизма (семафор), чтобы не перегружать РГБ/API
        for future in asyncio.as_completed(tasks):
            idx, res = await future
            raw_isbn = isbn_list[idx]
            # Определяем статусы для отображения (не обязательно точно, можно по результату)
            # Для простоты выведем по факту наличия res
            google_status = "✅" if res and res['source'] == 'Google Books' else "❌"
            open_status = "✅" if res and res['source'] == 'Open Library' else "❌"
            rsl_status = "✅" if res and res['source'] == 'РГБ' else "❌"
            if res:
                status_msg = f"✅ Найдено ({res['source']})"
                results[idx] = res
            else:
                status_msg = "❌ Не найдено"
                remaining_isbns.append(raw_isbn)
                remaining_indices.append(idx)
            # Вывод строки таблицы (нумеруем от 1 до total)
            print(f"{idx+1:4} | {raw_isbn:<20} | {google_status:^12} | {open_status:^12} | {rsl_status:^8} | {status_msg}")

    return results, remaining_isbns, remaining_indices


# ==================== ИНТЕГРИРОВАННАЯ ФУНКЦИЯ ПОИСКА ====================
def search_book_by_isbn(isbn: str, config: Optional[ScraperConfig] = None) -> Optional[Dict[str, Any]]:
    """Комбинированный поиск одной книги (синхронная версия, для одиночного вызова)."""
    norm_isbn = normalize_isbn(isbn)
    if not norm_isbn:
        print(f"⚠️ Некорректный ISBN: {isbn}")
        return None

    print(f"🔍 {isbn}:")
    res = get_from_google_books(norm_isbn)
    if res:
        print(f"   → Google Books ✅ {res['title']}")
        return res
    else:
        print("   → Google Books ❌ не найдено")

    res = get_from_open_library(norm_isbn)
    if res:
        print(f"   → Open Library ✅ {res['title']}")
        return res
    else:
        print("   → Open Library ❌ не найдено")

    res = get_from_rsl(isbn)
    if res:
        print(f"   → РГБ ✅ {res['title']}")
        return res
    else:
        print("   → РГБ ❌ не найдено")

    print(f"   → Запуск скрапера для ISBN {isbn}")
    if config is None:
        config = ScraperConfig()
    with RussianBookScraperUC(config) as scraper:
        return scraper.search_by_isbn(isbn)


def search_multiple_books(isbn_list: List[str], config: Optional[ScraperConfig] = None) -> List[Optional[Dict[str, Any]]]:
    """
    Поиск нескольких ISBN: сначала параллельный этап API и РГБ (через asyncio),
    для оставшихся — параллельный скрапинг.
    """
    if config is None:
        config = ScraperConfig()

    # Запускаем асинхронный этап API/РГБ
    results, remaining_isbns, remaining_indices = asyncio.run(run_api_stage(isbn_list, config))

    if remaining_indices:
        print(f"\n🔍 Запуск скрапера для {len(remaining_indices)} ISBN, не найденных через API/РГБ")
        scraped_results = async_parallel_search(remaining_isbns, config)
        for idx, res in zip(remaining_indices, scraped_results):
            results[idx] = res

    return results


# ==================== ТАБЛИЧНЫЙ ВЫВОД ====================
def print_results_table(isbn_list: List[str], results: List[Optional[Dict[str, Any]]]):
    """Красивый вывод итоговых результатов."""
    print("\n" + "="*130)
    header = f"{'ISBN':<20} {'Название':<40} {'Автор(ы)':<30} {'Стр.':<6} {'Год':<5} {'Источник':<15}"
    print(header)
    print("="*130)
    for i, res in enumerate(results):
        if res:
            authors_str = ", ".join(res.get('authors', []))
            title = (res['title'][:37] + "...") if len(res['title']) > 40 else res['title']
            authors = (authors_str[:27] + "...") if len(authors_str) > 30 else authors_str

            pages = res.get('pages')
            if pages is None:
                pages = '—'
            else:
                pages = str(pages)

            year = res.get('year')
            if year is None:
                year = '—'
            else:
                year = str(year)

            source = res.get('source')
            if source is None:
                source = 'неизвестно'
            else:
                source = str(source)

            print(f"{isbn_list[i]:<20} {title:<40} {authors:<30} {pages:<6} {year:<5} {source:<15}")
        else:
            print(f"{isbn_list[i]:<20} {'❌ не найдена':<40} {'':<30} {'':<6} {'':<5} {'':<15}")
    print("="*130)


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================
if __name__ == "__main__":
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
        api_max_concurrent=5   # ограничение параллельных запросов к API/РГБ для стабильности
    )

    try:
        with open("isbn_list.txt", "r", encoding="utf-8") as f:
            # Читаем все строки, удаляем пустые и дубликаты с сохранением порядка
            seen = set()
            unique_isbns = []
            for line in f:
                isbn = line.strip()
                if isbn and isbn not in seen:
                    seen.add(isbn)
                    unique_isbns.append(isbn)
            isbn_list = unique_isbns
    except FileNotFoundError:
        print("Файл isbn_list.txt не найден. Использую тестовый список.")
        isbn_list = [
            "978-5-907144-52-1",
            "978-0-13-417327-6",
            "978-5-04-089765-3",
            "978-5-699-93966-0"
        ]

    start = time.time()
    results = search_multiple_books(isbn_list, config)
    print(f"\nОбщее время: {time.time() - start:.2f}с")
    print_results_table(isbn_list, results)