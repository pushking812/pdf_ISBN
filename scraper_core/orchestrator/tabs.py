"""
Менеджер вкладок браузера для параллельного скрапинга.

Управляет созданием, мониторингом и балансировкой нагрузки между вкладками браузера.
Интегрируется с SearchCoordinator для оптимального распределения задач по ресурсам.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class TabState(Enum):
    """Состояния вкладки."""

    INIT = "init"  # Инициализирована, но не активна
    READY = "ready"  # Готова к выполнению задачи
    BUSY = "busy"  # Выполняет задачу
    WAITING = "waiting"  # Ожидает ответа от ресурса
    ERROR = "error"  # Ошибка при выполнении
    COMPLETED = "completed"  # Задача выполнена успешно
    TIMEOUT = "timeout"  # Превышено время ожидания


@dataclass
class TabInfo:
    """Информация о вкладке браузера."""

    tab_id: str  # Уникальный идентификатор вкладки
    handle: str  # Handle вкладки в драйвере
    state: TabState = TabState.INIT  # Текущее состояние
    task_id: Optional[str] = None  # ID выполняемой задачи (если есть)
    isbn: Optional[str] = None  # ISBN текущей задачи
    resource_id: Optional[str] = None  # Ресурс текущей задачи
    started_at: Optional[datetime] = None  # Время начала выполнения
    error: Optional[str] = None  # Сообщение об ошибке (если есть)
    result: Optional[Dict[str, Any]] = None  # Результат выполнения


class TabManager:
    """
    Менеджер вкладок браузера.

    Управляет созданием, распределением задач и мониторингом состояния вкладок.
    """

    def __init__(
        self,
        max_tabs: int = 5,
        tab_switch_delay: float = 0.2,
        monitor_interval: float = 1.0,
        load_balancing_threshold: float = 0.8,
    ):
        """
        Инициализация менеджера вкладок.

        Args:
            max_tabs: Максимальное количество одновременных вкладок
            tab_switch_delay: Задержка при переключении между вкладками (секунды)
            monitor_interval: Интервал мониторинга состояния вкладок (секунды)
            load_balancing_threshold: Порог для балансировки нагрузки (0.0-1.0)
        """
        self.max_tabs = max_tabs
        self.tab_switch_delay = tab_switch_delay
        self.monitor_interval = monitor_interval
        self.load_balancing_threshold = load_balancing_threshold

        # Состояние менеджера
        self.tabs: Dict[str, TabInfo] = {}  # tab_id -> TabInfo
        self.driver = None  # WebDriver будет установлен позже
        self.search_coordinator = None  # Будет установлен позже
        self.retry_handler = None  # Будет установлен позже

        # Мониторинг
        self.monitor_task: Optional[asyncio.Task] = None
        self.is_running = False

        logger.info(f"TabManager инициализирован с max_tabs={max_tabs}")

    async def initialize(self, driver, search_coordinator=None, retry_handler=None):
        """
        Инициализация менеджера с драйвером и зависимостями.

        Args:
            driver: WebDriver для управления браузером
            search_coordinator: SearchCoordinator для получения информации о ресурсах
            retry_handler: RetryHandler для обработки ошибок
        """
        self.driver = driver
        self.search_coordinator = search_coordinator
        self.retry_handler = retry_handler

        # Создаем начальные вкладки
        await self._create_initial_tabs()

        # Запускаем мониторинг
        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_tabs())

        logger.info("TabManager инициализирован с драйвером и зависимостями")

    async def _create_initial_tabs(self):
        """Создание начальных вкладок."""
        if not self.driver:
            raise RuntimeError("Драйвер не инициализирован")

        # Сохраняем основную вкладку
        main_handle = self.driver.current_window_handle
        main_tab = TabInfo(tab_id="tab_0", handle=main_handle, state=TabState.READY)
        self.tabs["tab_0"] = main_tab

        # Создаем дополнительные вкладки
        for i in range(1, self.max_tabs):
            try:
                # Переключаемся на основную вкладку перед созданием новой
                self.driver.switch_to.window(main_handle)
                await asyncio.sleep(self.tab_switch_delay)

                # Создаем новую вкладку
                self.driver.switch_to.new_window("tab")
                await asyncio.sleep(self.tab_switch_delay)

                new_handle = self.driver.current_window_handle
                tab_id = f"tab_{i}"
                new_tab = TabInfo(
                    tab_id=tab_id, handle=new_handle, state=TabState.READY
                )
                self.tabs[tab_id] = new_tab

                logger.debug(f"Создана вкладка {tab_id} с handle {new_handle}")
            except Exception as e:
                logger.error(f"Ошибка при создании вкладки {i}: {e}")
                break

        # Возвращаемся на основную вкладку
        self.driver.switch_to.window(main_handle)
        logger.info(f"Создано {len(self.tabs)} вкладок")

    async def execute_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Выполнение списка задач через вкладки.

        Args:
            tasks: Список задач для выполнения

        Returns:
            Список результатов выполнения задач
        """
        if not self.driver:
            raise RuntimeError("TabManager не инициализирован")

        logger.info(f"Начало выполнения {len(tasks)} задач через TabManager")

        results = []
        pending_tasks = tasks.copy()

        while pending_tasks:
            # Находим свободную вкладку
            free_tab = self._find_free_tab()
            if not free_tab:
                # Нет свободных вкладок, ждем
                await asyncio.sleep(0.1)
                continue

            # Берем следующую задачу
            task = pending_tasks.pop(0)

            try:
                # Выполняем задачу через вкладку
                result = await self._execute_task_on_tab(free_tab, task)
                results.append(result)

                # Освобождаем вкладку
                free_tab.state = TabState.READY
                free_tab.task_id = None
                free_tab.isbn = None
                free_tab.resource_id = None
                free_tab.started_at = None

            except Exception as e:
                logger.error(f"Ошибка при выполнении задачи {task.get('isbn')}: {e}")
                # Помечаем вкладку как ошибочную
                free_tab.state = TabState.ERROR
                free_tab.error = str(e)
                # Пытаемся восстановить вкладку
                await self._recover_tab(free_tab)

        logger.info(f"Выполнение завершено: {len(results)} результатов")
        return results

    def _find_free_tab(self) -> Optional[TabInfo]:
        """Поиск свободной вкладки."""
        for tab in self.tabs.values():
            if tab.state == TabState.READY:
                return tab
        return None

    def get_available_tab(self) -> Optional[TabInfo]:
        """
        Получение доступной вкладки (публичный метод).
        
        Returns:
            TabInfo или None если нет доступных вкладок
        """
        return self._find_free_tab()

    async def assign_task_to_tab(
        self, tab_id: str, isbn: str, resource_id: str, url: str
    ) -> bool:
        """
        Назначение задачи на вкладку (публичный метод).
        
        Args:
            tab_id: ID вкладки
            isbn: ISBN для поиска
            resource_id: ID ресурса
            url: URL для загрузки
            
        Returns:
            True если задача назначена успешно
        """
        if tab_id not in self.tabs:
            logger.error(f"Вкладка {tab_id} не найдена")
            return False
            
        tab = self.tabs[tab_id]
        if tab.state != TabState.READY:
            logger.error(f"Вкладка {tab_id} не готова (состояние: {tab.state})")
            return False
            
        # Создаем задачу
        task = {
            "task_id": f"{isbn}_{resource_id}",
            "isbn": isbn,
            "resource_id": resource_id,
            "url": url
        }
        
        # Выполняем задачу
        try:
            result = await self._execute_task_on_tab(tab, task)
            tab.result = result
            tab.state = TabState.COMPLETED
            return True
        except Exception as e:
            logger.error(f"Ошибка выполнения задачи на вкладке {tab_id}: {e}")
            tab.error = str(e)
            tab.state = TabState.ERROR
            return False

    async def wait_for_task_completion(self, tab_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """
        Ожидание завершения задачи на вкладке.
        
        Args:
            tab_id: ID вкладки
            timeout: Таймаут ожидания в секундах
            
        Returns:
            Результат задачи или None
        """
        if tab_id not in self.tabs:
            return None
            
        tab = self.tabs[tab_id]
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            if tab.state in (TabState.COMPLETED, TabState.ERROR, TabState.TIMEOUT):
                if tab.state == TabState.COMPLETED:
                    return {
                        "success": True,
                        "data": tab.result or {},
                        "html": tab.result.get("_html", "") if tab.result else "",
                        "tab_id": tab_id
                    }
                else:
                    return {
                        "success": False,
                        "error": tab.error or "Unknown error",
                        "tab_id": tab_id
                    }
            await asyncio.sleep(0.1)
            
        # Таймаут
        tab.state = TabState.TIMEOUT
        tab.error = "Timeout waiting for task completion"
        return {
            "success": False,
            "error": "Timeout",
            "tab_id": tab_id
        }

    async def _execute_task_on_tab(
        self, tab: TabInfo, task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Выполнение задачи на указанной вкладке.

        Args:
            tab: Вкладка для выполнения
            task: Задача для выполнения

        Returns:
            Результат выполнения задачи
        """
        # Обновляем состояние вкладки
        tab.state = TabState.BUSY
        tab.task_id = task.get("task_id")
        tab.isbn = task.get("isbn")
        tab.resource_id = task.get("resource_id")
        tab.started_at = datetime.now()
        tab.error = None
        tab.result = None

        logger.debug(f"Выполнение задачи {task.get('isbn')} на вкладке {tab.tab_id}")

        try:
            # Переключаемся на вкладку
            self.driver.switch_to.window(tab.handle)
            await asyncio.sleep(self.tab_switch_delay)

            # Получаем информацию о ресурсе (если доступно)
            resource_config = None
            if self.search_coordinator and tab.resource_id:
                # Проверяем, есть ли метод get_resource_config
                if hasattr(self.search_coordinator, 'get_resource_config'):
                    try:
                        resource_config = self.search_coordinator.get_resource_config(
                            tab.resource_id
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось получить конфигурацию ресурса {tab.resource_id}: {e}")
                else:
                    logger.debug(f"SearchCoordinator не имеет метода get_resource_config, пропускаем")

            # Выполняем поиск
            result = await self._perform_search(tab, task, resource_config)

            # Обновляем результат
            tab.result = result
            tab.state = TabState.COMPLETED

            logger.debug(
                f"Задача {task.get('isbn')} выполнена успешно на вкладке {tab.tab_id}"
            )
            return result

        except Exception as e:
            tab.state = TabState.ERROR
            tab.error = str(e)
            logger.error(f"Ошибка при выполнении задачи на вкладке {tab.tab_id}: {e}")
            raise

    async def _perform_search(
        self,
        tab: TabInfo,
        task: Dict[str, Any],
        resource_config: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Выполнение поиска на вкладке.

        Args:
            tab: Вкладка для выполнения
            task: Задача для выполнения
            resource_config: Конфигурация ресурса

        Returns:
            Результат поиска
        """
        # Это заглушка - реальная логика будет реализована позже
        # с интеграцией с WebResourceHandler

        isbn = task.get("isbn", "")
        resource_id = task.get("resource_id", "unknown")

        # Имитация выполнения поиска
        await asyncio.sleep(0.5)

        return {
            "isbn": isbn,
            "resource_id": resource_id,
            "title": f"Книга {isbn}",
            "authors": ["Автор неизвестен"],
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "tab_id": tab.tab_id,
        }

    async def _recover_tab(self, tab: TabInfo):
        """
        Восстановление вкладки после ошибки.

        Args:
            tab: Вкладка для восстановления
        """
        logger.debug(f"Попытка восстановления вкладки {tab.tab_id}")

        try:
            # Пытаемся перезагрузить страницу
            self.driver.switch_to.window(tab.handle)
            self.driver.get("about:blank")
            await asyncio.sleep(0.5)

            # Сбрасываем состояние
            tab.state = TabState.READY
            tab.error = None
            tab.result = None
            tab.task_id = None
            tab.isbn = None
            tab.resource_id = None
            tab.started_at = None

            logger.info(f"Вкладка {tab.tab_id} восстановлена")

        except Exception as e:
            logger.error(f"Не удалось восстановить вкладку {tab.tab_id}: {e}")
            # Помечаем вкладку как нерабочую
            tab.state = TabState.ERROR

    async def _monitor_tabs(self):
        """Мониторинг состояния вкладок."""
        logger.info("Запуск мониторинга вкладок")

        while self.is_running:
            try:
                await self._check_tab_health()
                await self._balance_load()
                await asyncio.sleep(self.monitor_interval)
            except Exception as e:
                logger.error(f"Ошибка в мониторинге вкладок: {e}")
                await asyncio.sleep(self.monitor_interval)

    async def _check_tab_health(self):
        """Проверка здоровья вкладок."""
        now = datetime.now()

        for tab in self.tabs.values():
            if tab.state == TabState.BUSY and tab.started_at:
                # Проверяем, не зависла ли вкладка
                elapsed = (now - tab.started_at).total_seconds()
                if elapsed > 30:  # 30 секунд таймаут
                    logger.warning(
                        f"Вкладка {tab.tab_id} зависла (таймаут {elapsed:.1f}с)"
                    )
                    tab.state = TabState.TIMEOUT
                    # Пытаемся восстановить
                    await self._recover_tab(tab)

    async def _balance_load(self):
        """Балансировка нагрузки между вкладками."""
        # Считаем статистику
        total_tabs = len(self.tabs)
        busy_tabs = sum(1 for tab in self.tabs.values() if tab.state == TabState.BUSY)

        if total_tabs == 0:
            return

        load_factor = busy_tabs / total_tabs

        # Если нагрузка превышает порог, логируем предупреждение
        if load_factor > self.load_balancing_threshold:
            logger.warning(
                f"Высокая нагрузка на вкладки: {busy_tabs}/{total_tabs} "
                f"({load_factor:.1%}) > {self.load_balancing_threshold:.1%}"
            )

    def get_tab_status(self) -> Dict[str, Any]:
        """
        Получение статуса всех вкладок.

        Returns:
            Словарь со статусом вкладок
        """
        status = {"total_tabs": len(self.tabs), "tabs": {}}

        for tab_id, tab in self.tabs.items():
            status["tabs"][tab_id] = {
                "state": tab.state.value,
                "task_id": tab.task_id,
                "isbn": tab.isbn,
                "resource_id": tab.resource_id,
                "started_at": tab.started_at.isoformat() if tab.started_at else None,
                "error": tab.error,
                "has_result": tab.result is not None,
            }

        return status

    async def close(self):
        """Закрытие менеджера вкладок."""
        logger.info("Закрытие TabManager")

        # Останавливаем мониторинг
        self.is_running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        # Закрываем вкладки (кроме основной)
        if self.driver:
            try:
                # Переключаемся на основную вкладку
                main_handle = None
                for tab in self.tabs.values():
                    if tab.tab_id == "tab_0":
                        main_handle = tab.handle
                        break

                if main_handle:
                    self.driver.switch_to.window(main_handle)

                    # Закрываем все остальные вкладки
                    for tab in self.tabs.values():
                        if tab.tab_id != "tab_0" and tab.handle != main_handle:
                            try:
                                self.driver.switch_to.window(tab.handle)
                                self.driver.close()
                            except Exception as e:
                                logger.debug(
                                    f"Не удалось закрыть вкладку {tab.tab_id}: {e}"
                                )

                    # Возвращаемся на основную вкладку
                    self.driver.switch_to.window(main_handle)
            except Exception as e:
                logger.error(f"Ошибка при закрытии вкладок: {e}")

        # Очищаем состояние
        self.tabs.clear()
        logger.info("TabManager закрыт")


# Утилитарные функции для работы с вкладками


def create_tab_manager_from_config(config: Dict[str, Any]) -> TabManager:
    """
    Создание TabManager из конфигурации.

    Args:
        config: Конфигурация TabManager

    Returns:
        Экземпляр TabManager
    """
    max_tabs = config.get("max_tabs", 5)
    tab_switch_delay = config.get("tab_switch_delay", 0.2)
    monitor_interval = config.get("monitor_interval", 1.0)
    load_balancing_threshold = config.get("load_balancing_threshold", 0.8)

    return TabManager(
        max_tabs=max_tabs,
        tab_switch_delay=tab_switch_delay,
        monitor_interval=monitor_interval,
        load_balancing_threshold=load_balancing_threshold,
    )
