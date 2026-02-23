"""
Обработчик веб-ресурсов (Selenium/requests).

Обрабатывает ресурсы, требующие загрузки через веб-браузер или HTTP-запросы.
"""

import asyncio
import random
from typing import Dict, Any, Optional
import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from .base import ResourceHandler
from ..parsers.selector_client import SelectorClient

logger = logging.getLogger(__name__)


class WebResourceHandler(ResourceHandler):
    """Обработчик веб-ресурсов."""

    def __init__(self, resource_config: Dict[str, Any], retry_handler=None):
        super().__init__(resource_config)
        self.selector_client = SelectorClient({})
        self.driver = None
        self.use_selenium = resource_config.get("use_selenium", True)
        self.delay_range = resource_config.get("delay_range", [0.5, 2.0])
        self.timeout = resource_config.get("timeout", 10)
        self.retry_handler = retry_handler
        self.resource_id = resource_config.get("id", "unknown")

    async def _random_delay(self):
        """Случайная задержка между действиями."""
        if self.delay_range:
            delay = random.uniform(*self.delay_range)
            await asyncio.sleep(delay)

    async def _create_driver(self):
        """Создание WebDriver при необходимости."""
        if not self.use_selenium or self.driver:
            return

        try:
            import undetected_chromedriver as uc

            options = uc.ChromeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")

            self.driver = uc.Chrome(options=options)
            logger.debug("Создан WebDriver для веб-ресурса")
        except ImportError:
            logger.warning("undetected_chromedriver не установлен, используем requests")
            self.use_selenium = False

    async def _close_driver(self):
        """Закрытие WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                logger.debug("WebDriver закрыт")
            except Exception as e:
                logger.error(f"Ошибка закрытия WebDriver: {e}")

    async def fetch_data(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Получение данных с веб-ресурса.

        Args:
            isbn: ISBN для поиска

        Returns:
            Optional[Dict[str, Any]]: Сырые данные или None
        """
        clean_isbn = isbn.replace("-", "").strip()
        search_url = self.resource_config.get("search_url_template", "").format(
            isbn=clean_isbn
        )

        if not search_url:
            logger.error(f"URL шаблон не найден для ресурса: {self.resource_id}")
            return None

        # Внутренняя функция для выполнения с повторными попытками
        async def _fetch_internal():
            if self.use_selenium:
                await self._create_driver()
                return await self._fetch_with_selenium(search_url, clean_isbn)
            else:
                return await self._fetch_with_requests(search_url, clean_isbn)

        try:
            if self.retry_handler:
                # Используем RetryHandler для выполнения с повторными попытками
                return await self.retry_handler.execute_with_retry(
                    _fetch_internal, resource_id=self.resource_id
                )
            else:
                # Без RetryHandler - обычное выполнение
                return await _fetch_internal()
        except Exception as e:
            logger.error(f"Ошибка получения данных для ISBN {isbn}: {e}")
            return None

    async def _fetch_with_selenium(
        self, search_url: str, isbn: str
    ) -> Optional[Dict[str, Any]]:
        """Получение данных с использованием Selenium."""
        try:
            # Загрузка главной страницы при необходимости
            if self.resource_config.get("need_main_page"):
                base_url = self.resource_config.get("base_url", "")
                if base_url:
                    self.driver.get(base_url)
                    await self._random_delay()
                    await self._handle_modals()

            # Загрузка страницы поиска
            self.driver.get(search_url)
            await self._random_delay()
            await self._handle_modals()

            # Проверка на страницу "ничего не найдено"
            if await self._check_no_results():
                logger.debug(f"Ничего не найдено для ISBN {isbn}")
                return None

            # Поиск ссылки на книгу
            book_url = await self._find_book_link()
            if not book_url:
                logger.debug(f"Ссылка на книгу не найдена для ISBN {isbn}")
                return None

            # Переход на страницу книги
            self.driver.get(book_url)
            await self._random_delay()

            # Получение HTML страницы
            html = self.driver.page_source
            current_url = self.driver.current_url

            return {
                "html": html,
                "url": current_url,
                "isbn": isbn,
                "resource_id": self.resource_id,
                "driver": self.driver,  # Для парсинга, который может использовать driver
            }
        except Exception as e:
            logger.error(f"Ошибка Selenium для ISBN {isbn}: {e}")
            return None

    async def _fetch_with_requests(
        self, search_url: str, isbn: str
    ) -> Optional[Dict[str, Any]]:
        """Получение данных с использованием requests."""
        try:
            import requests
            from bs4 import BeautifulSoup

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(search_url, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            html = response.text
            soup = BeautifulSoup(html, "lxml")

            # Проверка на страницу "ничего не найдено"
            no_product_phrases = self.resource_config.get("no_product_phrases", [])
            page_text = soup.get_text().lower()
            if any(
                phrase.lower() in page_text for phrase in no_product_phrases if phrase
            ):
                return None

            # Поиск ссылки на книгу
            book_url = self._find_book_link_in_soup(soup, search_url)
            if not book_url:
                return None

            # Загрузка страницы книги
            book_response = requests.get(
                book_url, headers=headers, timeout=self.timeout
            )
            book_response.raise_for_status()

            return {
                "html": book_response.text,
                "url": book_url,
                "isbn": isbn,
                "resource_id": self.resource_id,
                "soup": BeautifulSoup(book_response.text, "lxml"),
            }
        except Exception as e:
            logger.error(f"Ошибка requests для ISBN {isbn}: {e}")
            return None

    async def _handle_modals(self):
        """Обработка модальных окон (город, куки и т.д.)."""
        if not self.driver:
            return

        try:
            # Пример: обработка модального окна выбора города
            city_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Да, я здесь')]")
                )
            )
            city_button.click()
            await self._random_delay()
            logger.debug("Модальное окно города обработано")
        except TimeoutException:
            pass  # Модального окна нет, это нормально

    async def _check_no_results(self) -> bool:
        """Проверка на страницу 'ничего не найдено'."""
        if not self.driver:
            return False

        page_source = self.driver.page_source.lower()
        no_product_phrases = self.resource_config.get("no_product_phrases", [])

        for phrase in no_product_phrases:
            if phrase and phrase.lower() in page_source:
                return True

        return False

    async def _find_book_link(self) -> Optional[str]:
        """Поиск ссылки на книгу на странице поиска."""
        if not self.driver:
            return None

        selectors = self.resource_config.get("product_link_selectors", [])

        for selector in selectors:
            try:
                element = WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return element.get_attribute("href")
            except TimeoutException:
                continue

        return None

    def _find_book_link_in_soup(self, soup, base_url: str) -> Optional[str]:
        """Поиск ссылки на книгу в BeautifulSoup."""
        import urllib.parse

        selectors = self.resource_config.get("product_link_selectors", [])

        for selector in selectors:
            element = soup.select_one(selector)
            if element and element.get("href"):
                href = element.get("href")
                # Преобразование относительного URL в абсолютный
                if href.startswith("/"):
                    parsed_base = urllib.parse.urlparse(base_url)
                    return f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                elif href.startswith("http"):
                    return href
                else:
                    # Относительный URL без ведущего слеша
                    return urllib.parse.urljoin(base_url, href)

        return None

    def parse_data(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Парсинг сырых данных с использованием селекторов.

        Args:
            raw_data: Сырые данные от fetch_data

        Returns:
            Optional[Dict[str, Any]]: Структурированные данные или None
        """
        if not raw_data or "html" not in raw_data:
            return None

        html = raw_data["html"]
        isbn = raw_data.get("isbn", "")
        resource_id = raw_data.get("resource_id", "")

        # Получаем селекторы из конфигурации ресурса
        selectors = self.resource_config.get("selectors", [])

        # Используем SelectorClient для извлечения данных
        result = self.selector_client.extract_with_selectors(
            html=html, selectors=selectors, resource_id=resource_id
        )

        if result:
            # Добавляем метаданные
            result.update(
                {
                    "isbn": isbn,
                    "resource_id": resource_id,
                    "url": raw_data.get("url", ""),
                    "source": self.resource_config.get("name", resource_id),
                    "confidence": result.get("confidence", 0.0),
                }
            )

        return result

    async def fetch_page(self, url: str) -> Optional[str]:
        """
        Загрузка страницы по URL и возврат HTML содержимого.

        Args:
            url: URL для загрузки

        Returns:
            HTML содержимое страницы или None при ошибке
        """
        try:
            if self.use_selenium:
                await self._create_driver()
                if not self.driver:
                    return None
                self.driver.get(url)
                await asyncio.sleep(random.uniform(*self.delay_range))
                return self.driver.page_source
            else:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.text()
                        else:
                            logger.warning(
                                f"Ошибка загрузки страницы {url}: {response.status}"
                            )
                            return None
        except Exception as e:
            logger.error(f"Ошибка при загрузке страницы {url}: {e}")
            return None

    async def close(self):
        """Закрытие ресурсов."""
        await self._close_driver()
