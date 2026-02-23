"""
Обработчик веб-ресурсов с использованием TabManager для управления вкладками.

Этот обработчик использует TabManager для работы с вкладками браузера вместо создания
отдельных окон для каждого ресурса.
"""

import asyncio
import random
import logging
from typing import Dict, Any, Optional

from .base import ResourceHandler
from ..parsers.selector_client import SelectorClient

logger = logging.getLogger(__name__)


class TabManagerWebResourceHandler(ResourceHandler):
    """Обработчик веб-ресурсов с использованием TabManager."""

    def __init__(
        self,
        resource_config: Dict[str, Any],
        tab_manager=None,
        retry_handler=None,
        driver_manager=None
    ):
        """
        Инициализация обработчика.

        Args:
            resource_config: Конфигурация ресурса
            tab_manager: TabManager для управления вкладками
            retry_handler: RetryHandler для обработки ошибок
            driver_manager: DriverManager для управления драйверами
        """
        super().__init__(resource_config)
        self.selector_client = SelectorClient({})
        self.tab_manager = tab_manager
        self.driver_manager = driver_manager
        self.use_selenium = resource_config.get("use_selenium", True)
        self.delay_range = resource_config.get("delay_range", [0.5, 2.0])
        self.timeout = resource_config.get("timeout", 10)
        self.retry_handler = retry_handler
        self.resource_id = resource_config.get("id", "unknown")
        
        # Если нет TabManager, используем стандартный подход
        if not self.tab_manager:
            logger.warning(f"TabManager не предоставлен для ресурса {self.resource_id}, "
                          "будет использован стандартный WebResourceHandler")
            self._fallback_handler = None

    async def _random_delay(self):
        """Случайная задержка между действиями."""
        if self.delay_range:
            delay = random.uniform(*self.delay_range)
            await asyncio.sleep(delay)

    async def _get_driver(self):
        """Получение драйвера через DriverManager или создание нового."""
        if self.driver_manager:
            return await self.driver_manager.get_driver()
        
        # Если нет DriverManager, создаем драйвер напрямую
        if not self.use_selenium:
            return None
            
        try:
            import undetected_chromedriver as uc
            options = uc.ChromeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            return uc.Chrome(options=options)
        except ImportError:
            logger.warning("undetected_chromedriver не установлен, используем requests")
            self.use_selenium = False
            return None

    async def _release_driver(self, driver):
        """Освобождение драйвера."""
        if self.driver_manager and driver:
            await self.driver_manager.release_driver(driver)

    async def fetch_data(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Получение данных с веб-ресурса с использованием TabManager.

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

        # Если есть TabManager, используем его
        if self.tab_manager and self.tab_manager.driver:
            return await self._fetch_with_tab_manager(search_url, clean_isbn)
        
        # Иначе используем стандартный подход
        return await self._fetch_without_tab_manager(search_url, clean_isbn)

    async def _fetch_with_tab_manager(self, search_url: str, isbn: str) -> Optional[Dict[str, Any]]:
        """Получение данных с использованием TabManager."""
        try:
            # Получаем свободную вкладку через TabManager
            tab_info = self.tab_manager.get_available_tab()
            if not tab_info:
                logger.warning(f"Нет доступных вкладок для ISBN {isbn}")
                return None

            # Назначаем задачу вкладке
            success = await self.tab_manager.assign_task_to_tab(
                tab_id=tab_info.tab_id,
                isbn=isbn,
                resource_id=self.resource_id,
                url=search_url
            )
            
            if not success:
                logger.error(f"Не удалось назначить задачу для ISBN {isbn} на вкладку {tab_info.tab_id}")
                return None

            # Ждем завершения задачи
            result = await self.tab_manager.wait_for_task_completion(tab_info.tab_id)
            
            if result and result.get("success"):
                return {
                    "_html": result.get("html", ""),
                    "_url": search_url,
                    "_isbn": isbn,
                    "_resource_id": self.resource_id,
                    "_tab_id": tab_info.tab_id,
                    **result.get("data", {})
                }
            else:
                logger.error(f"Задача не выполнена для ISBN {isbn} в табе {tab_info.tab_id}")
                return None

        except Exception as e:
            logger.error(f"Ошибка получения данных через TabManager для ISBN {isbn}: {e}")
            return None

    async def _fetch_without_tab_manager(self, search_url: str, isbn: str) -> Optional[Dict[str, Any]]:
        """Получение данных без TabManager, но с использованием общего драйвера."""
        # Если есть драйвер от TabManager, используем его
        if self.tab_manager and self.tab_manager.driver:
            try:
                driver = self.tab_manager.driver
                # Просто загружаем страницу через существующий драйвер
                # (это будет использовать текущую вкладку, что не идеально, но лучше чем новое окно)
                driver.get(search_url)
                await asyncio.sleep(2)  # Базовая задержка
                
                html = driver.page_source
                return {
                    "_html": html,
                    "_url": search_url,
                    "_isbn": isbn,
                    "_resource_id": self.resource_id
                }
            except Exception as e:
                logger.error(f"Ошибка загрузки страницы через общий драйвер: {e}")
                return None
        else:
            # Если нет драйвера, возвращаем None - лучше не создавать новое окно
            logger.warning(f"Нет доступного драйвера для ISBN {isbn}, пропускаем")
            return None

    async def _fetch_with_selenium(self, driver, search_url: str, isbn: str) -> Optional[Dict[str, Any]]:
        """Получение данных с использованием Selenium (для fallback)."""
        try:
            driver.get(search_url)
            await asyncio.sleep(2)  # Базовая задержка для загрузки
            
            # Проверяем наличие результатов
            html = driver.page_source
            
            # Базовый парсинг
            result = {
                "_html": html,
                "_url": search_url,
                "_isbn": isbn,
                "_resource_id": self.resource_id
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка Selenium для ISBN {isbn}: {e}")
            return None

    def parse_data(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Парсинг сырых данных.

        Args:
            raw_data: Сырые данные из fetch_data

        Returns:
            Optional[Dict[str, Any]]: Структурированные данные или None
        """
        if not raw_data:
            return None

        # Используем SelectorClient для извлечения данных
        html = raw_data.get("_html", "")
        if not html:
            return None

        try:
            # Извлекаем данные с использованием селекторов из конфигурации
            selectors = self.resource_config.get("selectors", {})
            extracted = self.selector_client.extract_data(html, selectors)
            
            # Добавляем метаданные
            result = {
                "isbn": raw_data.get("_isbn", ""),
                "resource_id": self.resource_id,
                "url": raw_data.get("_url", ""),
                "timestamp": asyncio.get_event_loop().time(),
                **extracted
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка парсинга данных для ресурса {self.resource_id}: {e}")
            return None

    async def process(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Полный процесс обработки ISBN.

        Args:
            isbn: ISBN для обработки

        Returns:
            Optional[Dict[str, Any]]: Результат обработки или None
        """
        try:
            # Получаем сырые данные
            raw_data = await self.fetch_data(isbn)
            if not raw_data:
                return None

            # Парсим данные
            parsed_data = self.parse_data(raw_data)
            
            # Добавляем метаданные о процессе
            if parsed_data:
                parsed_data["_processing_time"] = asyncio.get_event_loop().time()
                parsed_data["_handler_type"] = "TabManagerWebResourceHandler"
                parsed_data["_used_tab_manager"] = self.tab_manager is not None
            
            return parsed_data

        except Exception as e:
            logger.error(f"Ошибка обработки ISBN {isbn}: {e}")
            return None