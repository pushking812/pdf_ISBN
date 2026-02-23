# Структура для будущего расширения TaskQueue с заглушками

## Цель
Создать расширяемую архитектуру для очереди задач, которая:
1. Позволяет легко внедрить приоритетную очередь в будущем
2. Сохраняет текущую функциональность
3. Минимизирует изменения в существующем коде

## Текущая реализация
В `ScraperOrchestrator` используется простая `asyncio.Queue`:
```python
self.task_queue: asyncio.Queue = asyncio.Queue()
```

## Предлагаемая архитектура

### 1. Интерфейс `TaskQueueInterface`
Создать абстрактный базовый класс в `scraper_core/orchestrator/queue.py`:
```python
class TaskQueueInterface(ABC):
    async def put(self, task: ScrapingTask, priority: TaskPriority = TaskPriority.MEDIUM) -> None
    async def get(self) -> ScrapingTask
    def task_done(self) -> None
    async def join(self) -> None
    def qsize(self) -> int
    def empty(self) -> bool
```

### 2. Перечисление приоритетов
```python
class TaskPriority(IntEnum):
    LOW = 3
    MEDIUM = 2
    HIGH = 1
    CRITICAL = 0
```

### 3. Простая реализация `SimpleTaskQueue`
Обертка над `asyncio.Queue`, игнорирующая приоритеты (для обратной совместимости):
```python
class SimpleTaskQueue(TaskQueueInterface):
    def __init__(self):
        self._queue = asyncio.Queue()
    
    async def put(self, task: ScrapingTask, priority: TaskPriority = TaskPriority.MEDIUM):
        # Приоритет игнорируется, но логируется для отладки
        await self._queue.put(task)
```

### 4. Заглушка для приоритетной очереди `PriorityTaskQueue`
```python
class PriorityTaskQueue(TaskQueueInterface):
    def __init__(self):
        self._fallback_queue = SimpleTaskQueue()
        logger.warning("PriorityTaskQueue пока не реализована")
```

### 5. Фабрика для создания очередей
```python
def create_task_queue(use_priority: bool = False) -> TaskQueueInterface:
    if use_priority:
        return PriorityTaskQueue()
    return SimpleTaskQueue()
```

## Изменения в `ScraperOrchestrator`

### 1. Импорт интерфейса
```python
from scraper_core.orchestrator.queue import TaskQueueInterface, create_task_queue
```

### 2. Изменение инициализации
Заменить:
```python
self.task_queue: asyncio.Queue = asyncio.Queue()
```
На:
```python
self.task_queue: TaskQueueInterface = create_task_queue(use_priority=False)
```

### 3. Обновление методов использования
Методы `put`, `get`, `task_done`, `join` остаются без изменений, так как интерфейс совместим.

### 4. Добавление поддержки приоритетов при создании задач
В методе `scrape_isbns` при добавлении задач:
```python
# Вместо: await self.task_queue.put(task)
priority = self._determine_task_priority(task)  # Метод для определения приоритета
await self.task_queue.put(task, priority)
```

## План внедрения

### Этап 1: Создание файлов и интерфейсов
1. Создать `scraper_core/orchestrator/queue.py` с интерфейсом и простой реализацией
2. Обновить `ScraperOrchestrator` для использования интерфейса
3. Протестировать, что функциональность не сломалась

### Этап 2: Добавление заглушек для будущего расширения
1. Создать `PriorityTaskQueue` как заглушку
2. Добавить фабрику `create_task_queue`
3. Добавить параметр конфигурации для выбора типа очереди

### Этап 3: Подготовка к реальной реализации приоритетов
1. Добавить поле `priority` в `ScrapingTask`
2. Добавить логику определения приоритета в `SearchCoordinator`
3. Собрать метрики для анализа необходимости приоритетов

## Обновление TODO.md

Переместить задачи по продвинутой очереди приоритетов в конец итерации A:

### Текущие задачи (оставить):
- [ ] **A.6.1**: Расширить `ScraperOrchestrator.task_queue` для поддержки приоритетов
- [ ] **A.6.4**: Написать тесты для системы очередей

### Новые задачи (добавить):
- [ ] **A.9.1**: Создать интерфейс `TaskQueueInterface` и `SimpleTaskQueue`
- [ ] **A.9.2**: Интегрировать интерфейс в `ScraperOrchestrator`
- [ ] **A.9.3**: Добавить заглушку `PriorityTaskQueue` для будущего расширения
- [ ] **A.9.4**: Добавить параметр конфигурации для выбора типа очереди

### Отложенные задачи (переместить в конец):
- [-] **A.5.2**: Определение требований к приоритетам задач
- [-] **A.5.3**: Проектирование системы приоритетов
- [ ] **A.10.1**: Реализовать настоящую `PriorityTaskQueue` с `heapq`
- [ ] **A.10.2**: Добавить стратегии определения приоритетов задач
- [ ] **A.10.3**: Протестировать производительность приоритетной очереди

## Преимущества подхода

1. **Обратная совместимость**: Текущий код продолжает работать без изменений
2. **Легкость расширения**: Для добавления приоритетной очереди нужно только реализовать `PriorityTaskQueue`
3. **Минимальные риски**: Изменения изолированы в отдельном модуле
4. **Гибкость**: Можно A/B тестировать разные реализации очередей
5. **Подготовка к будущему**: Интерфейс уже готов для расширения

## Следующие шаги

1. Переключиться в режим Code для реализации
2. Создать файл `queue.py` с предложенной структурой
3. Обновить `ScraperOrchestrator`
4. Обновить `TODO.md` с новой структурой задач
5. Протестировать интеграцию