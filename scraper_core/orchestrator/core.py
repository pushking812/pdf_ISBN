"""
Оркестратор скрапинга.

Управляет процессом скрапинга: распределение задач между ресурсами,
управление вкладками браузера, обработка ошибок.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from scraper_core.config.loader import ConfigLoader
from scraper_core.config.base import ScraperEnvConfig, ResourceConfig
from scraper_core.handlers.factory import ResourceHandlerFactory
from scraper_core.parsers.selector_client import SelectorClient
from scraper_core.integration.selector_integration import SelectorIntegration
from scraper_core.isbn.processor import ISBNProcessor
from scraper_core.orchestrator.search import SearchCoordinator
from scraper_core.orchestrator.tabs import TabManager
from scraper_core.orchestrator.retry import RetryHandler, RetryConfig
from scraper_core.orchestrator.drivers import (
    DriverManagerInterface,
    SimpleDriverManager,
    DriverConfig,
)
from scraper_core.orchestrator.antibot import (
    AntiBotHandlerInterface,
    SimpleAntiBotHandler,
    AntiBotConfig,
)
from scraper_core.orchestrator.queue import (
    TaskQueueInterface,
    create_task_queue,
    TaskPriority,
)

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Статусы задач."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ScrapingTask:
    """Задача скрапинга."""

    isbn: str
    resource_id: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ScraperOrchestrator:
    """Оркестратор скрапинга."""

    def __init__(
        self,
        config_dir: str = "config",
        max_concurrent_tasks: int = 3,
        enable_auto_generation: bool = True,
        use_search_coordinator: bool = True,
        use_tab_manager: bool = True,
        use_retry_handler: bool = True,
        use_driver_manager: bool = False,
        use_antibot_handler: bool = False,
        use_priority_queue: bool = False,
        retry_config: Optional[RetryConfig] = None,
        driver_config: Optional[DriverConfig] = None,
        antibot_config: Optional[AntiBotConfig] = None,
        max_tabs: int = 5,
    ):
        """
        Инициализация оркестратора.

        Args:
            config_dir: Директория с конфигурационными файлами
            max_concurrent_tasks: Максимальное количество одновременных задач
            enable_auto_generation: Включить автоматическую генерацию селекторов
            use_search_coordinator: Использовать SearchCoordinator для оптимизации выбора ресурсов
            use_tab_manager: Использовать TabManager для управления вкладками браузера
            use_retry_handler: Использовать RetryHandler для обработки ошибок
            use_driver_manager: Использовать DriverManager для управления драйверами
            use_antibot_handler: Использовать AntiBotHandler для обхода блокировок
            use_priority_queue: Использовать очередь с приоритетами (если False - простая очередь)
            retry_config: Конфигурация RetryHandler (опционально)
            driver_config: Конфигурация DriverManager (опционально)
            antibot_config: Конфигурация AntiBotHandler (опционально)
            max_tabs: Максимальное количество вкладок для TabManager
        """
        self.config_dir = config_dir
        self.max_concurrent_tasks = max_concurrent_tasks
        self.enable_auto_generation = enable_auto_generation
        self.use_search_coordinator = use_search_coordinator
        self.use_tab_manager = use_tab_manager
        self.use_retry_handler = use_retry_handler
        self.use_driver_manager = use_driver_manager
        self.use_antibot_handler = use_antibot_handler
        self.use_priority_queue = use_priority_queue

        # Загрузка конфигурации
        self.config_loader = ConfigLoader(config_dir)
        self.env_config: ScraperEnvConfig = self.config_loader.load_env_config()
        self.resources_config: Dict[str, ResourceConfig] = (
            self.config_loader.load_resources_config()
        )

        # Инициализация компонентов
        self.isbn_processor = ISBNProcessor()
        self.selector_client = SelectorClient({})
        self.selector_integration = SelectorIntegration(config_dir)
        self.handler_factory = ResourceHandlerFactory()

        # Инициализация SearchCoordinator
        self.search_coordinator: Optional[SearchCoordinator] = None
        if use_search_coordinator:
            self.search_coordinator = SearchCoordinator(
                config_loader=self.config_loader,
                enabled_resources=self.env_config.enabled_resources,
            )
            logger.info("SearchCoordinator инициализирован")

        # Инициализация RetryHandler
        self.retry_handler: Optional[RetryHandler] = None
        if use_retry_handler:
            self.retry_handler = RetryHandler(retry_config or RetryConfig())
            logger.info("RetryHandler инициализирован")

        # Инициализация TabManager
        self.tab_manager: Optional[TabManager] = None
        if use_tab_manager:
            self.tab_manager = TabManager(max_tabs=max_tabs)
            logger.info(f"TabManager инициализирован с max_tabs={max_tabs}")

        # Инициализация DriverManager
        self.driver_manager: Optional[DriverManagerInterface] = None
        if use_driver_manager:
            self.driver_manager = SimpleDriverManager(driver_config or DriverConfig())
            logger.info("DriverManager инициализирован")

        # Инициализация AntiBotHandler
        self.antibot_handler: Optional[AntiBotHandlerInterface] = None
        if use_antibot_handler:
            self.antibot_handler = SimpleAntiBotHandler(
                antibot_config or AntiBotConfig()
            )
            logger.info("AntiBotHandler инициализирован")

        # Состояние оркестратора
        self.active_tasks: Set[str] = set()
        self.task_queue: TaskQueueInterface = create_task_queue(
            use_priority=use_priority_queue
        )
        self.results: List[Dict[str, Any]] = []

        logger.info(
            f"Оркестратор инициализирован с {len(self.resources_config)} ресурсами, "
            f"use_tab_manager={use_tab_manager}, use_retry_handler={use_retry_handler}, "
            f"use_driver_manager={use_driver_manager}, use_antibot_handler={use_antibot_handler}, "
            f"use_priority_queue={use_priority_queue}"
        )

    async def scrape_isbns(self, isbns: List[str]) -> List[Dict[str, Any]]:
        """
        Скрапинг списка ISBN.

        Args:
            isbns: Список ISBN номеров

        Returns:
            List[Dict[str, Any]]: Результаты скрапинга
        """
        logger.info(f"Начало скрапинга {len(isbns)} ISBN")

        # Инициализация TabManager с драйвером если используется
        if self.use_tab_manager and self.tab_manager and not self.tab_manager.driver:
            try:
                # Создаем драйвер для TabManager
                import undetected_chromedriver as uc
                options = uc.ChromeOptions()
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--no-sandbox")
                
                # Настройки для работы с вкладками
                options.add_argument("--disable-popup-blocking")
                
                driver = uc.Chrome(options=options)
                await self.tab_manager.initialize(
                    driver=driver,
                    search_coordinator=self.search_coordinator,
                    retry_handler=self.retry_handler
                )
                logger.info("TabManager инициализирован с драйвером")
            except ImportError as e:
                logger.warning(f"Не удалось создать драйвер для TabManager: {e}")
                self.use_tab_manager = False
            except Exception as e:
                logger.error(f"Ошибка инициализации TabManager: {e}")
                self.use_tab_manager = False

        # Нормализация и валидация ISBN
        validated_isbns = []
        for isbn in isbns:
            normalized = self.isbn_processor.normalize_isbn(isbn)
            if normalized and self.isbn_processor.validate_isbn(normalized):
                validated_isbns.append(normalized)
            else:
                logger.warning(f"Некорректный ISBN: {isbn}")

        if not validated_isbns:
            logger.warning("Нет валидных ISBN для скрапинга")
            return []

        # Создание задач с использованием SearchCoordinator или полного перебора
        tasks = []
        if self.search_coordinator:
            # Используем SearchCoordinator для выбора оптимальных ресурсов
            for isbn in validated_isbns:
                tried_resources: Set[str] = set()
                max_attempts = min(3, len(self.env_config.enabled_resources))

                for attempt in range(max_attempts):
                    resource_id = self.search_coordinator.get_next_resource(
                        task_isbn=isbn, tried_resources=tried_resources
                    )

                    if not resource_id:
                        logger.warning(f"Для ISBN {isbn} не найдено доступных ресурсов")
                        break

                    task = ScrapingTask(isbn=isbn, resource_id=resource_id)

                    # Определение приоритета задачи на основе конфигурации ресурса
                    priority = TaskPriority.MEDIUM
                    resource_config = self.resources_config.get(resource_id)
                    if resource_config:
                        resource_priority = getattr(
                            resource_config, "priority", 2
                        )  # 2 = MEDIUM по умолчанию
                        if resource_priority == 1:
                            priority = TaskPriority.HIGH
                        elif resource_priority == 3:
                            priority = TaskPriority.LOW
                        elif resource_priority == 0:
                            priority = TaskPriority.CRITICAL

                    await self.task_queue.put(task, priority=priority)
                    tasks.append(task)
                    tried_resources.add(resource_id)

                    # Если ресурс высокого приоритета, создаем только одну задачу
                    if attempt == 0 and priority == TaskPriority.HIGH:
                        logger.debug(
                            f"Для ISBN {isbn} выбран ресурс высокого приоритета {resource_id}"
                        )
                        break
        else:
            # Старая логика: создаем задачи для всех комбинаций ISBN и ресурсов
            for isbn in validated_isbns:
                for resource_id in self.env_config.enabled_resources:
                    if resource_id in self.resources_config:
                        task = ScrapingTask(isbn=isbn, resource_id=resource_id)
                        await self.task_queue.put(task)
                        tasks.append(task)

        logger.info(f"Создано {len(tasks)} задач скрапинга")

        # Запуск воркеров
        workers = [
            asyncio.create_task(self._worker(worker_id))
            for worker_id in range(self.max_concurrent_tasks)
        ]

        # Ожидание завершения всех задач
        await self.task_queue.join()

        # Отмена воркеров
        for worker in workers:
            worker.cancel()

        # Сбор результатов
        completed_tasks = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        failed_tasks = [t for t in tasks if t.status == TaskStatus.FAILED]

        logger.info(
            f"Скрапинг завершен: {len(completed_tasks)} успешно, {len(failed_tasks)} с ошибками"
        )

        # Возвращаем результаты успешных задач
        return [task.result for task in completed_tasks if task.result]

    async def _worker(self, worker_id: int):
        """Воркер для обработки задач."""
        logger.debug(f"Воркер {worker_id} запущен")

        while True:
            try:
                task = await self.task_queue.get()

                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()

                logger.debug(
                    f"Воркер {worker_id} обрабатывает ISBN {task.isbn} для ресурса {task.resource_id}"
                )

                start_time = datetime.now()
                success = False
                error_message = None
                rate_limited = False

                try:
                    result = await self._scrape_single_isbn(task.isbn, task.resource_id)
                    task.result = result
                    task.status = TaskStatus.COMPLETED
                    success = True
                    logger.debug(
                        f"Воркер {worker_id} успешно обработал ISBN {task.isbn}"
                    )
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    error_message = str(e)
                    logger.error(
                        f"Воркер {worker_id} ошибка при обработке ISBN {task.isbn}: {e}"
                    )

                    # Определяем, была ли блокировка по rate limit
                    if (
                        "rate limit" in error_message.lower()
                        or "blocked" in error_message.lower()
                    ):
                        rate_limited = True
                finally:
                    task.completed_at = datetime.now()
                    self.task_queue.task_done()

                    # Обновляем статистику в SearchCoordinator
                    if self.search_coordinator:
                        response_time = (datetime.now() - start_time).total_seconds()
                        self.search_coordinator.update_resource_stats(
                            resource_id=task.resource_id,
                            success=success,
                            response_time=response_time,
                            error_message=error_message,
                            rate_limited=rate_limited,
                        )

            except asyncio.CancelledError:
                logger.debug(f"Воркер {worker_id} остановлен")
                break
            except Exception as e:
                logger.error(f"Воркер {worker_id} критическая ошибка: {e}")
                self.task_queue.task_done()

    async def _scrape_single_isbn(
        self, isbn: str, resource_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Скрапинг одного ISBN для указанного ресурса.

        Args:
            isbn: ISBN номер
            resource_id: Идентификатор ресурса

        Returns:
            Optional[Dict[str, Any]]: Результат скрапинга или None
        """
        resource = self.resources_config.get(resource_id)
        if not resource:
            logger.error(f"Ресурс {resource_id} не найден в конфигурации")
            return None

        # Создание обработчика ресурса с передачей TabManager и RetryHandler
        # Преобразуем ResourceConfig в словарь для совместимости
        resource_dict = resource.dict() if hasattr(resource, 'dict') else resource
        
        # Для веб-ресурсов используем TabManagerWebResourceHandler если доступен TabManager
        handler = None
        resource_type = resource_dict.get("type", "").lower()
        
        if resource_type == "web" and self.use_tab_manager and self.tab_manager:
            try:
                from scraper_core.handlers.tab_manager_handler import TabManagerWebResourceHandler
                handler = TabManagerWebResourceHandler(
                    resource_config=resource_dict,
                    tab_manager=self.tab_manager,
                    retry_handler=self.retry_handler,
                    driver_manager=self.driver_manager
                )
                logger.debug(f"Используем TabManagerWebResourceHandler для ресурса {resource_id}")
            except ImportError as e:
                logger.warning(f"Не удалось импортировать TabManagerWebResourceHandler: {e}")
                # Продолжаем со стандартным обработчиком
        
        # Если обработчик не создан через TabManager, используем фабрику
        if not handler:
            handler = self.handler_factory.create_handler(
                resource_dict, retry_handler=self.retry_handler
            )
        
        if not handler:
            logger.error(f"Не удалось создать обработчик для ресурса {resource_id}")
            return None

        try:
            # Выполнение скрапинга через обработчик
            # Используем метод process из базового класса ResourceHandler
            result = await handler.process(isbn)

            # Если есть результат, обновляем селекторы
            if result and self.enable_auto_generation:
                await self._update_selectors_from_result(resource_id, result)

            return result

        except Exception as e:
            logger.error(f"Ошибка скрапинга ISBN {isbn} на ресурсе {resource_id}: {e}")
            return None

    async def _update_selectors_from_result(
        self, resource_id: str, result: Dict[str, Any]
    ):
        """
        Обновление селекторов на основе результата скрапинга.

        Args:
            resource_id: Идентификатор ресурса
            result: Результат скрапинга
        """
        try:
            # Получаем HTML из результата (если есть)
            html = result.get("_html")
            if not html:
                return

            # Обновляем селекторы
            updated = self.selector_integration.update_resource_selectors(
                resource_id=resource_id, html=html, force_regenerate=False
            )

            if updated:
                logger.info(
                    f"Обновлено {len(updated)} селекторов для ресурса {resource_id}"
                )

        except Exception as e:
            logger.error(
                f"Ошибка при обновлении селекторов для ресурса {resource_id}: {e}"
            )

    def get_resource_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение статистики по ресурсам.

        Returns:
            Dict[str, Dict[str, Any]]: Статистика по ресурсам
        """
        stats = {}
        for resource_id, resource in self.resources_config.items():
            stats[resource_id] = {
                "name": resource.name,
                "type": resource.type,
                "selectors_count": len(resource.selectors),
                "has_test_data": resource.test_data is not None,
                "enabled": resource_id in self.env_config.enabled_resources,
            }
        return stats

    async def close(self):
        """Закрытие ресурсов оркестратора."""
        # Очистка очереди
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
                self.task_queue.task_done()
            except asyncio.QueueEmpty:
                break

        # Закрытие TabManager
        if self.tab_manager:
            try:
                await self.tab_manager.close()
                logger.debug("TabManager закрыт")
            except Exception as e:
                logger.error(f"Ошибка закрытия TabManager: {e}")

        # Закрытие DriverManager
        if self.driver_manager:
            await self.driver_manager.cleanup()
            logger.debug("DriverManager очищен")

        # Закрытие TabManager
        if self.tab_manager:
            await self.tab_manager.close()
            logger.debug("TabManager закрыт")

        logger.info("Оркестратор закрыт")
