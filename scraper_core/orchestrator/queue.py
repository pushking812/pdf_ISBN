"""
Очередь задач для оркестратора скрапинга.

Предоставляет абстракцию для управления очередями задач с поддержкой приоритетов
и возможностью легкого расширения в будущем.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scraper_core.orchestrator.core import ScrapingTask

logger = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    """Приоритеты задач."""

    LOW = 3
    MEDIUM = 2
    HIGH = 1
    CRITICAL = 0  # Самый высокий приоритет


@dataclass
class PrioritizedTask:
    """Задача с приоритетом."""

    task: ScrapingTask
    priority: TaskPriority = TaskPriority.MEDIUM
    added_at: float = 0.0  # Время добавления (для разрешения ties)


class TaskQueueInterface(ABC):
    """Интерфейс очереди задач."""

    @abstractmethod
    async def put(
        self, task: ScrapingTask, priority: TaskPriority = TaskPriority.MEDIUM
    ) -> None:
        """Добавить задачу в очередь с указанным приоритетом."""
        pass

    @abstractmethod
    async def get(self) -> ScrapingTask:
        """Получить следующую задачу из очереди."""
        pass

    @abstractmethod
    def task_done(self) -> None:
        """Пометить задачу как выполненную."""
        pass

    @abstractmethod
    async def join(self) -> None:
        """Дождаться завершения всех задач."""
        pass

    @abstractmethod
    def qsize(self) -> int:
        """Текущий размер очереди."""
        pass

    @abstractmethod
    def empty(self) -> bool:
        """Пуста ли очередь."""
        pass


class SimpleTaskQueue(TaskQueueInterface):
    """
    Простая реализация очереди задач на основе asyncio.Queue.

    Не поддерживает настоящие приоритеты, но сохраняет интерфейс
    для будущего расширения.
    """

    def __init__(self):
        self._queue = None  # Создадим лениво при первом использовании
        self._priority_logging = True  # Логировать приоритеты для отладки

    def _ensure_queue(self):
        """Создать очередь, если она еще не создана."""
        if self._queue is None:
            # Создаем очередь с использованием текущего event loop
            # Если loop не существует, будет создан при первом асинхронном вызове
            self._queue = asyncio.Queue()

    async def put(
        self, task: ScrapingTask, priority: TaskPriority = TaskPriority.MEDIUM
    ) -> None:
        """Добавить задачу в очередь (приоритет игнорируется в текущей реализации)."""
        self._ensure_queue()
        if self._priority_logging and priority != TaskPriority.MEDIUM:
            logger.debug(
                f"Задача для ISBN {task.isbn} добавлена с приоритетом {priority.name} "
                f"(приоритеты пока не поддерживаются)"
            )
        await self._queue.put(task)

    async def get(self) -> ScrapingTask:
        """Получить следующую задачу из очереди (FIFO)."""
        self._ensure_queue()
        return await self._queue.get()

    def task_done(self) -> None:
        """Пометить задачу как выполненную."""
        self._ensure_queue()
        self._queue.task_done()

    async def join(self) -> None:
        """Дождаться завершения всех задач."""
        self._ensure_queue()
        await self._queue.join()

    def qsize(self) -> int:
        """Текущий размер очереди."""
        self._ensure_queue()
        return self._queue.qsize()

    def empty(self) -> bool:
        """Пуста ли очередь."""
        self._ensure_queue()
        return self._queue.empty()


class PriorityTaskQueue(TaskQueueInterface):
    """
    Очередь с поддержкой приоритетов (заглушка для будущей реализации).

    TODO: Реализовать с использованием heapq или asyncio.PriorityQueue
    """

    def __init__(self):
        # Временная заглушка - не создаем реальную PriorityQueue, чтобы избежать ошибок event loop
        # self._queue будет создан при необходимости в будущей реализации
        self._queue = None
        logger.warning(
            "PriorityTaskQueue пока не реализована, использует SimpleTaskQueue"
        )
        self._fallback_queue = SimpleTaskQueue()

    async def put(
        self, task: ScrapingTask, priority: TaskPriority = TaskPriority.MEDIUM
    ) -> None:
        """Добавить задачу с приоритетом (заглушка)."""
        # Временная реализация - используем fallback
        await self._fallback_queue.put(task, priority)

    async def get(self) -> ScrapingTask:
        """Получить следующую задачу (заглушка)."""
        return await self._fallback_queue.get()

    def task_done(self) -> None:
        """Пометить задачу как выполненную."""
        self._fallback_queue.task_done()

    async def join(self) -> None:
        """Дождаться завершения всех задач."""
        await self._fallback_queue.join()

    def qsize(self) -> int:
        """Текущий размер очереди."""
        return self._fallback_queue.qsize()

    def empty(self) -> bool:
        """Пуста ли очередь."""
        return self._fallback_queue.empty()


# Фабрика для создания очередей
def create_task_queue(use_priority: bool = False) -> TaskQueueInterface:
    """
    Создать очередь задач.

    Args:
        use_priority: Использовать ли очередь с приоритетами (если False - простая очередь)

    Returns:
        TaskQueueInterface: Экземпляр очереди задач
    """
    if use_priority:
        return PriorityTaskQueue()
    else:
        return SimpleTaskQueue()
