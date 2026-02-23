"""
Тесты для системы очередей задач.
"""

import asyncio
import logging
import pytest

from scraper_core.orchestrator.queue import (
    TaskQueueInterface,
    SimpleTaskQueue,
    PriorityTaskQueue,
    TaskPriority,
    create_task_queue,
)
from scraper_core.orchestrator.core import ScrapingTask, TaskStatus


class TestTaskPriority:
    """Тесты приоритетов задач."""

    def test_priority_values(self):
        """Проверка значений приоритетов."""
        assert TaskPriority.CRITICAL == 0
        assert TaskPriority.HIGH == 1
        assert TaskPriority.MEDIUM == 2
        assert TaskPriority.LOW == 3

        # Проверка порядка приоритетов
        assert (
            TaskPriority.CRITICAL
            < TaskPriority.HIGH
            < TaskPriority.MEDIUM
            < TaskPriority.LOW
        )


class TestSimpleTaskQueue:
    """Тесты простой очереди задач."""

    @pytest.fixture
    def queue(self):
        """Фикстура для создания очереди."""
        return SimpleTaskQueue()

    @pytest.fixture
    def sample_task(self):
        """Фикстура для создания тестовой задачи."""
        return ScrapingTask(isbn="9781234567890", resource_id="test_resource")

    @pytest.mark.asyncio
    async def test_put_and_get(self, queue, sample_task):
        """Тест добавления и извлечения задачи."""
        # Добавляем задачу
        await queue.put(sample_task, priority=TaskPriority.HIGH)

        # Проверяем размер очереди
        assert queue.qsize() == 1
        assert not queue.empty()

        # Извлекаем задачу
        retrieved_task = await queue.get()

        # Проверяем, что задача та же
        assert retrieved_task.isbn == sample_task.isbn
        assert retrieved_task.resource_id == sample_task.resource_id

        # Проверяем, что очередь пуста
        assert queue.qsize() == 0
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_multiple_tasks_fifo(self, queue):
        """Тест порядка извлечения задач (FIFO)."""
        tasks = [
            ScrapingTask(isbn="9781111111111", resource_id="resource1"),
            ScrapingTask(isbn="9782222222222", resource_id="resource2"),
            ScrapingTask(isbn="9783333333333", resource_id="resource3"),
        ]

        # Добавляем задачи
        for task in tasks:
            await queue.put(task)

        # Извлекаем и проверяем порядок
        for i, expected_task in enumerate(tasks):
            retrieved_task = await queue.get()
            assert retrieved_task.isbn == expected_task.isbn
            assert queue.qsize() == len(tasks) - i - 1

        assert queue.empty()

    @pytest.mark.asyncio
    async def test_task_done_and_join(self, queue, sample_task):
        """Тест завершения задач и ожидания."""
        # Добавляем несколько задач
        for i in range(3):
            task = ScrapingTask(
                isbn=f"978{i}{i}{i}{i}{i}{i}{i}{i}{i}{i}", resource_id=f"resource{i}"
            )
            await queue.put(task)

        # Извлекаем и отмечаем как выполненные
        for _ in range(3):
            task = await queue.get()
            queue.task_done()

        # join должен завершиться сразу, так как все задачи выполнены
        await queue.join()

        # Очередь пуста
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_priority_ignored_in_simple_queue(self, queue, sample_task, caplog):
        """Тест, что приоритеты игнорируются в простой очереди (только логирование)."""
        # Добавляем задачу с высоким приоритетом
        await queue.put(sample_task, priority=TaskPriority.HIGH)

        # Проверяем, что задача добавлена
        assert queue.qsize() == 1

        # Извлекаем задачу
        retrieved_task = await queue.get()
        assert retrieved_task.isbn == sample_task.isbn

    def test_qsize_and_empty(self, queue, sample_task):
        """Тест методов qsize и empty."""
        # Изначально очередь пуста
        assert queue.qsize() == 0
        assert queue.empty()

        # Добавляем задачу синхронно (через создание future)
        async def add_task():
            await queue.put(sample_task)

        asyncio.run(add_task())

        # Проверяем размер
        assert queue.qsize() == 1
        assert not queue.empty()

        # Извлекаем задачу
        async def get_task():
            return await queue.get()

        task = asyncio.run(get_task())
        assert task.isbn == sample_task.isbn

        # Снова пусто
        assert queue.qsize() == 0
        assert queue.empty()


class TestPriorityTaskQueue:
    """Тесты очереди с приоритетами (заглушка)."""

    @pytest.fixture
    def queue(self):
        """Фикстура для создания очереди с приоритетами."""
        return PriorityTaskQueue()

    @pytest.fixture
    def sample_task(self):
        """Фикстура для создания тестовой задачи."""
        return ScrapingTask(isbn="9781234567890", resource_id="test_resource")

    @pytest.mark.asyncio
    async def test_priority_queue_is_stub(self, sample_task, caplog):
        """Тест, что PriorityTaskQueue является заглушкой и использует SimpleTaskQueue."""
        # Создаем очередь внутри теста, чтобы логи попали в caplog
        with caplog.at_level(logging.WARNING):
            queue = PriorityTaskQueue()
            # Проверяем, что при создании выводится предупреждение
            assert "PriorityTaskQueue пока не реализована" in caplog.text

        # Проверяем, что очередь работает (через fallback)
        await queue.put(sample_task, priority=TaskPriority.HIGH)
        assert queue.qsize() == 1

        retrieved_task = await queue.get()
        assert retrieved_task.isbn == sample_task.isbn

        queue.task_done()
        await queue.join()

    def test_priority_queue_interface(self, queue):
        """Тест, что PriorityTaskQueue реализует интерфейс TaskQueueInterface."""
        assert isinstance(queue, TaskQueueInterface)
        assert hasattr(queue, "put")
        assert hasattr(queue, "get")
        assert hasattr(queue, "task_done")
        assert hasattr(queue, "join")
        assert hasattr(queue, "qsize")
        assert hasattr(queue, "empty")


class TestCreateTaskQueue:
    """Тесты фабрики создания очередей."""

    def test_create_simple_queue(self):
        """Тест создания простой очереди."""
        queue = create_task_queue(use_priority=False)
        assert isinstance(queue, SimpleTaskQueue)
        assert not isinstance(queue, PriorityTaskQueue)

    def test_create_priority_queue(self):
        """Тест создания очереди с приоритетами."""
        queue = create_task_queue(use_priority=True)
        assert isinstance(queue, PriorityTaskQueue)
        # PriorityTaskQueue использует SimpleTaskQueue внутри, но это нормально для заглушки

    def test_default_is_simple_queue(self):
        """Тест, что по умолчанию создается простая очередь."""
        queue = create_task_queue()  # без параметров
        assert isinstance(queue, SimpleTaskQueue)


class TestIntegrationWithScrapingTask:
    """Интеграционные тесты с ScrapingTask."""

    @pytest.mark.asyncio
    async def test_queue_with_real_scraping_tasks(self):
        """Тест очереди с реальными задачами скрапинга."""
        queue = SimpleTaskQueue()

        tasks = [
            ScrapingTask(
                isbn="9781111111111", resource_id="resource1", status=TaskStatus.PENDING
            ),
            ScrapingTask(
                isbn="9782222222222", resource_id="resource2", status=TaskStatus.PENDING
            ),
            ScrapingTask(
                isbn="9783333333333", resource_id="resource3", status=TaskStatus.PENDING
            ),
        ]

        # Добавляем задачи с разными приоритетами
        await queue.put(tasks[0], priority=TaskPriority.HIGH)
        await queue.put(tasks[1], priority=TaskPriority.MEDIUM)
        await queue.put(tasks[2], priority=TaskPriority.LOW)

        # Извлекаем задачи
        retrieved_tasks = []
        for _ in range(3):
            task = await queue.get()
            retrieved_tasks.append(task)
            queue.task_done()

        # Проверяем, что все задачи извлечены
        assert len(retrieved_tasks) == 3

        # Проверяем, что это те же задачи (по ISBN)
        isbns = {task.isbn for task in retrieved_tasks}
        expected_isbns = {task.isbn for task in tasks}
        assert isbns == expected_isbns

        await queue.join()


@pytest.mark.asyncio
async def test_concurrent_access():
    """Тест конкурентного доступа к очереди."""
    queue = SimpleTaskQueue()

    # Количество задач и воркеров
    num_tasks = 10
    num_workers = 3

    # Создаем задачи
    tasks = [
        ScrapingTask(isbn=f"978{i:010d}", resource_id=f"resource{i % 3}")
        for i in range(num_tasks)
    ]

    # Добавляем задачи конкурентно
    async def producer():
        for task in tasks:
            await queue.put(task)
            await asyncio.sleep(0.001)  # небольшая задержка

    # Счетчик обработанных задач
    processed_count = 0

    async def consumer(worker_id):
        nonlocal processed_count
        while True:
            try:
                # Таймаут для избежания бесконечного ожидания
                task = await asyncio.wait_for(queue.get(), timeout=1.0)
                processed_count += 1
                queue.task_done()
                await asyncio.sleep(0.005)  # имитация обработки
            except asyncio.TimeoutError:
                break

    # Запускаем продюсера и консьюмеров
    await producer()

    workers = [consumer(i) for i in range(num_workers)]
    await asyncio.gather(*workers)

    # Проверяем, что все задачи обработаны
    assert processed_count == num_tasks
    assert queue.empty()

    # join должен завершиться
    await queue.join()
