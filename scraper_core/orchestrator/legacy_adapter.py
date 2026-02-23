"""
Адаптер для совместимости с существующим кодом scraper.py.

Этот модуль предоставляет интерфейсы, совместимые с существующими функциями scraper.py,
но использующие новую архитектуру оркестратора.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from enum import Enum

from scraper_core.orchestrator.core import ScraperOrchestrator
from scraper_core.config.loader import ConfigLoader
from scraper_core.isbn.processor import ISBNProcessor
from scraper_core.integration.dual_write import DualWriteCacheManager

logger = logging.getLogger(__name__)


class TabState(Enum):
    """Состояния вкладки (совместимость с существующим кодом)."""

    INIT = 0
    SEARCHING = 1
    BOOK_PAGE = 2
    DONE = 3
    ERROR = 4
    RATE_LIMITED = 5


class TabInfo:
    """Информация о вкладке (совместимость с существующим кодом)."""

    def __init__(self, isbn: str, handle: str, index: int, config: Any):
        self.isbn = isbn
        self.handle = handle
        self.index = index
        self.state = TabState.INIT
        self.result = None
        self.error = None
        self.book_url = None
        self.search_start_time = None
        self.timeout = getattr(config, "wait_product_link", 10)
        self.start_resource_index = 0
        self.tried_resources = 0
        self.accumulated_data = {}


class LegacyScraperAdapter:
    """
    Адаптер для использования новой архитектуры оркестратора
    с существующим интерфейсом scraper.py.
    """

    def __init__(
        self,
        config_dir: str = "config",
        max_concurrent_tasks: int = 3,
        enable_dual_write: bool = True,
        isbn_cache_path: str = "isbn_data_cache.json",
        pdf_cache_path: str = "pdf_isbn_cache.json",
    ):
        """
        Инициализация адаптера.

        Args:
            config_dir: Директория с конфигурационными файлами
            max_concurrent_tasks: Максимальное количество параллельных задач
            enable_dual_write: Включить ли dual-write в старые кэши
            isbn_cache_path: Путь к старому кэшу данных книг
            pdf_cache_path: Путь к старому кэшу PDF-ISBN
        """
        self.orchestrator = ScraperOrchestrator(
            config_dir=config_dir, max_concurrent_tasks=max_concurrent_tasks
        )
        self.config_loader = ConfigLoader(config_dir)
        self.isbn_processor = ISBNProcessor()

        # Инициализация менеджера dual-write
        self.dual_write_manager = DualWriteCacheManager(
            isbn_cache_path=isbn_cache_path,
            pdf_cache_path=pdf_cache_path,
            enable_dual_write=enable_dual_write,
        )

        logger.debug(
            f"LegacyScraperAdapter инициализирован с dual-write: {enable_dual_write}"
        )

    async def async_parallel_search(
        self, isbn_list: List[str], config: Optional[Any] = None
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Асинхронный параллельный поиск по списку ISBN.
        Совместим с существующей функцией async_parallel_search из scraper.py.

        Args:
            isbn_list: Список ISBN для поиска
            config: Конфигурация скрапера (опционально, для совместимости)

        Returns:
            Список результатов для каждого ISBN
        """
        # Нормализуем ISBN
        normalized_isbns = []
        for isbn in isbn_list:
            norm_isbn = self.isbn_processor.normalize_isbn(isbn)
            if norm_isbn:
                normalized_isbns.append(norm_isbn)
            else:
                normalized_isbns.append(isbn)

        # Используем оркестратор для скрапинга
        results = await self.orchestrator.scrape_isbns(normalized_isbns)

        # Преобразуем результаты в формат, совместимый с существующим кодом
        legacy_results = []
        for isbn, result in zip(normalized_isbns, results):
            if result:
                legacy_result = {
                    "title": result.get("title", "Не удалось определить название"),
                    "authors": result.get("authors", ["Неизвестный автор"]),
                    "pages": result.get("pages", "не указано"),
                    "year": result.get("year", "не указан"),
                    "url": result.get("url", ""),
                    "source": result.get("source", "Неизвестный источник"),
                    "isbn": result.get("isbn", isbn),
                    "resource_id": result.get("resource_id", ""),
                    "confidence": result.get("confidence", 0.0),
                }
                legacy_results.append(legacy_result)

                # Сохраняем данные в старый кэш через dual-write
                self._save_to_dual_write_cache(isbn, result)
            else:
                legacy_results.append(None)

        return legacy_results

    async def process_isbn_async(
        self,
        raw_isbn: str,
        config: Optional[Any] = None,
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Обработка одного ISBN (асинхронно).
        Совместим с существующей функцией process_isbn_async из scraper.py.

        Args:
            raw_isbn: ISBN для обработки
            config: Конфигурация скрапера (опционально)
            semaphore: Семафор для ограничения параллелизма (опционально)

        Returns:
            Результат скрапинга или None
        """
        # Нормализуем ISBN
        norm_isbn = self.isbn_processor.normalize_isbn(raw_isbn)
        if not norm_isbn:
            return None

        # Используем оркестратор для скрапинга одного ISBN
        results = await self.orchestrator.scrape_isbns([norm_isbn])

        if results and results[0]:
            result = results[0]
            legacy_result = {
                "title": result.get("title", "Не удалось определить название"),
                "authors": result.get("authors", ["Неизвестный автор"]),
                "pages": result.get("pages", "не указано"),
                "year": result.get("year", "не указан"),
                "url": result.get("url", ""),
                "source": result.get("source", "Неизвестный источник"),
                "isbn": norm_isbn,
                "resource_id": result.get("resource_id", ""),
                "confidence": result.get("confidence", 0.0),
            }

            # Сохраняем данные в старый кэш через dual-write
            self._save_to_dual_write_cache(norm_isbn, result)

            return legacy_result

        return None

    async def run_api_stage(
        self,
        isbn_list: List[str],
        config: Optional[Any] = None,
        connector: Optional[Any] = None,
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Запуск API-стадии (Google Books, Open Library).
        Совместим с существующей функцией run_api_stage из scraper.py.

        Args:
            isbn_list: Список ISBN для поиска через API
            config: Конфигурация скрапера (опционально)
            connector: Коннектор aiohttp (опционально)

        Returns:
            Список результатов API
        """
        # TODO: Интегрировать API-клиенты из новой архитектуры
        # Пока возвращаем пустые результаты для совместимости
        return [None] * len(isbn_list)

    def search_multiple_books(
        self, isbn_list: List[str], config: Optional[Any] = None
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Синхронный поиск по нескольким ISBN.
        Совместим с существующей функцией search_multiple_books из scraper.py.

        Args:
            isbn_list: Список ISBN для поиска
            config: Конфигурация скрапера (опционально)

        Returns:
            Список результатов
        """
        # Создаем event loop для синхронного вызова
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            results = loop.run_until_complete(
                self.async_parallel_search(isbn_list, config)
            )
            return results
        finally:
            loop.close()

    def save_pdf_data(
        self,
        pdf_key: str,
        pdf_data: Dict[str, Any],
    ) -> bool:
        """
        Сохраняет данные PDF-ISBN в старый кэш через dual-write.

        Args:
            pdf_key: Ключ PDF в формате "filename|filesize"
            pdf_data: Данные PDF в формате новой архитектуры

        Returns:
            True если данные сохранены
        """
        return self.dual_write_manager.save_pdf_data(pdf_key, pdf_data)

    def batch_save_isbn_data(
        self,
        isbn_data: Dict[str, Dict[str, Any]],
        only_if_complete: bool = True,
    ) -> int:
        """
        Пакетное сохранение данных книг в старый кэш через dual-write.

        Args:
            isbn_data: Словарь ISBN -> данные книги
            only_if_complete: Сохранять только если данные полные

        Returns:
            Количество сохраненных записей
        """
        return self.dual_write_manager.batch_save_isbn_data(isbn_data, only_if_complete)

    def _save_to_dual_write_cache(self, isbn: str, result: Dict[str, Any]) -> bool:
        """
        Сохраняет результат скрапинга в старый кэш через dual-write.

        Args:
            isbn: ISBN книги
            result: Результат скрапинга

        Returns:
            True если данные сохранены
        """
        try:
            # Подготавливаем данные для сохранения
            book_data = {
                "title": result.get("title", ""),
                "authors": result.get("authors", []),
                "pages": result.get("pages"),
                "year": result.get("year"),
                "source": result.get("source", "unknown"),
                "url": result.get("url", ""),
                "resource_id": result.get("resource_id", ""),
                "confidence": result.get("confidence", 0.0),
            }

            # Сохраняем через dual-write
            return self.dual_write_manager.save_isbn_data(
                isbn, book_data, only_if_complete=True
            )
        except Exception as e:
            logger.warning(
                f"Ошибка при сохранении в dual-write кэш для ISBN {isbn}: {e}"
            )
            return False

    async def close(self):
        """Закрытие ресурсов оркестратора."""
        await self.orchestrator.close()


# Функции для прямой замены существующих функций
async def async_parallel_search(
    isbn_list: List[str], config: Optional[Any] = None
) -> List[Optional[Dict[str, Any]]]:
    """
    Замена существующей функции async_parallel_search.
    Использует новую архитектуру оркестратора.
    """
    adapter = LegacyScraperAdapter()
    try:
        results = await adapter.async_parallel_search(isbn_list, config)
        return results
    finally:
        await adapter.close()


async def process_isbn_async(
    raw_isbn: str,
    config: Optional[Any] = None,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> Optional[Dict[str, Any]]:
    """
    Замена существующей функции process_isbn_async.
    Использует новую архитектуру оркестратора.
    """
    adapter = LegacyScraperAdapter()
    try:
        result = await adapter.process_isbn_async(raw_isbn, config, semaphore)
        return result
    finally:
        await adapter.close()


async def run_api_stage(
    isbn_list: List[str], config: Optional[Any] = None, connector: Optional[Any] = None
) -> List[Optional[Dict[str, Any]]]:
    """
    Замена существующей функции run_api_stage.
    Использует новую архитектуру оркестратора.
    """
    adapter = LegacyScraperAdapter()
    try:
        results = await adapter.run_api_stage(isbn_list, config, connector)
        return results
    finally:
        await adapter.close()


def search_multiple_books(
    isbn_list: List[str], config: Optional[Any] = None
) -> List[Optional[Dict[str, Any]]]:
    """
    Замена существующей функции search_multiple_books.
    Использует новую архитектуру оркестратора.
    """
    adapter = LegacyScraperAdapter()
    try:
        results = adapter.search_multiple_books(isbn_list, config)
        return results
    finally:
        # Для синхронного вызова нужно закрыть асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(adapter.close())
        finally:
            loop.close()


# Экспорт для обратной совместимости
__all__ = [
    "TabState",
    "TabInfo",
    "LegacyScraperAdapter",
    "async_parallel_search",
    "process_isbn_async",
    "run_api_stage",
    "search_multiple_books",
]
