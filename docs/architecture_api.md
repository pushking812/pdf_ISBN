# Документация по API новой архитектуры скрапинга

## Обзор

Новая архитектура скрапинга представляет собой модульную систему, построенную вокруг оркестратора, который координирует работу различных компонентов. Архитектура спроектирована для обеспечения высокой производительности, надежности и расширяемости.

## Основные компоненты

### 1. ScraperOrchestrator

Центральный компонент, управляющий всем процессом скрапинга.

#### Класс: `ScraperOrchestrator`

**Расположение:** `scraper_core/orchestrator/core.py`

**Инициализация:**
```python
from scraper_core.orchestrator.core import ScraperOrchestrator

orchestrator = ScraperOrchestrator(
    config_dir="config",
    max_concurrent_tasks=3,
    enable_auto_generation=True,
    use_search_coordinator=True,
    use_tab_manager=True,
    use_retry_handler=True,
    use_driver_manager=False,
    use_antibot_handler=False,
    use_priority_queue=False,
    max_tabs=5
)
```

**Основные методы:**

- `async def scrape_isbns(self, isbns: List[str], resources: Optional[List[str]] = None) -> Dict[str, Any]`
  - Основной метод для скрапинга списка ISBN
  - Возвращает словарь с результатами

- `async def scrape_single_isbn(self, isbn: str, resource_id: str) -> Dict[str, Any]`
  - Скрапинг одного ISBN на конкретном ресурсе

- `def get_metrics(self) -> Dict[str, Any]`
  - Получение метрик производительности

- `async def shutdown(self)`
  - Корректное завершение работы оркестратора

### 2. SearchCoordinator

Координатор поиска, оптимизирующий выбор ресурсов и распределение задач.

#### Класс: `SearchCoordinator`

**Расположение:** `scraper_core/orchestrator/search.py`

**Основные методы:**
- `async def get_next_resource(self, isbn: str, excluded_resources: Set[str] = None) -> Optional[str]`
  - Выбор следующего ресурса для обработки ISBN
- `def update_resource_stats(self, resource_id: str, success: bool, processing_time: float)`
  - Обновление статистики ресурса
- `def get_resource_priority(self, resource_id: str) -> float`
  - Получение приоритета ресурса

### 3. TabManager

Менеджер вкладок браузера для эффективного управления параллельными запросами.

#### Класс: `TabManager`

**Расположение:** `scraper_core/orchestrator/tabs.py`

**Основные методы:**
- `async def acquire_tab(self, resource_id: str) -> Any`
  - Получение свободной вкладки для ресурса
- `async def release_tab(self, tab_id: str)`
  - Освобождение вкладки
- `async def close_all_tabs(self)`
  - Закрытие всех вкладок

### 4. RetryHandler

Обработчик повторных попыток с экспоненциальным backoff.

#### Класс: `RetryHandler`

**Расположение:** `scraper_core/orchestrator/retry.py`

**Основные методы:**
- `async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any`
  - Выполнение функции с повторными попытками
- `def should_retry(self, exception: Exception) -> bool`
  - Проверка, требует ли исключение повторной попытки

### 5. DriverManager

Менеджер драйверов для централизованного управления Selenium/Playwright драйверами.

#### Интерфейс: `DriverManagerInterface`
#### Реализация: `SimpleDriverManager`

**Расположение:** `scraper_core/orchestrator/drivers.py`

**Основные методы:**
- `async def get_driver(self, resource_id: str) -> Any`
  - Получение драйвера для ресурса
- `async def release_driver(self, driver: Any)`
  - Освобождение драйвера
- `async def cleanup(self)`
  - Очистка всех драйверов

### 6. AntiBotHandler

Обработчик анти-бот защиты с стратегиями обхода блокировок.

#### Интерфейс: `AntiBotHandlerInterface`
#### Реализация: `SimpleAntiBotHandler`

**Расположение:** `scraper_core/orchestrator/antibot.py`

**Основные методы:**
- `async def apply_protection(self, driver: Any, resource_id: str)`
  - Применение защитных мер для драйвера
- `def detect_blocking(self, response: Any) -> bool`
  - Обнаружение блокировок
- `async def handle_blocking(self, driver: Any, resource_id: str)`
  - Обработка обнаруженных блокировок

### 7. TaskQueue

Система очередей задач с поддержкой приоритетов.

#### Интерфейс: `TaskQueueInterface`
#### Реализации: `SimpleTaskQueue`, `PriorityTaskQueue`

**Расположение:** `scraper_core/orchestrator/queue.py`

**Основные методы:**
- `async def put(self, task: Any, priority: TaskPriority = TaskPriority.NORMAL)`
  - Добавление задачи в очередь
- `async def get(self) -> Any`
  - Получение задачи из очереди
- `def task_done(self)`
  - Отметка задачи как выполненной
- `def qsize(self) -> int`
  - Получение размера очереди

### 8. LinkCollector

Коллектор ссылок для сбора и валидации URL.

#### Класс: `LinkCollector`

**Расположение:** `scraper_core/orchestrator/links.py`

**Основные методы:**
- `async def collect_links(self, html: str, base_url: str) -> List[str]`
  - Сбор ссылок из HTML
- `def filter_links(self, links: List[str], patterns: List[str]) -> List[str]`
  - Фильтрация ссылок по паттернам
- `def validate_url(self, url: str) -> bool`
  - Валидация URL

## Обработчики ресурсов

### Базовый класс: `BaseResourceHandler`

**Расположение:** `scraper_core/handlers/base.py`

**Основные методы:**
- `async def scrape(self, isbn: str) -> Dict[str, Any]`
  - Основной метод скрапинга
- `async def validate_response(self, response: Any) -> bool`
  - Валидация ответа
- `async def extract_data(self, response: Any) -> Dict[str, Any]`
  - Извлечение данных из ответа

### Конкретные обработчики:

1. **WebResourceHandler** - веб-скрапинг через Selenium/requests
2. **ApiResourceHandler** - работа с REST API
3. **JsonLdResourceHandler** - парсинг структурированных данных JSON-LD
4. **TableResourceHandler** - обработка табличных данных

## Конфигурационная система

### ConfigLoader

**Расположение:** `scraper_core/config/loader.py`

**Основные методы:**
- `def load_scraper_config() -> ScraperEnvConfig`
  - Загрузка конфигурации скрапера
- `def load_resource_config(resource_id: str) -> ResourceConfig`
  - Загрузка конфигурации ресурса
- `def save_selector_config(resource_id: str, selectors: Dict[str, Any])`
  - Сохранение конфигурации селекторов

### Модели конфигурации:

- `ScraperEnvConfig` - общая конфигурация
- `ResourceConfig` - конфигурация ресурса
- `SelectorConfig` - конфигурация селекторов

## Интеграционные компоненты

### 1. LegacyScraperAdapter

Адаптер для обратной совместимости со старым кодом.

**Расположение:** `scraper_core/orchestrator/legacy_adapter.py`

**Основные методы:**
- `async def async_parallel_search(self, isbns: List[str], **kwargs) -> Dict[str, Any]`
  - Эмуляция старого интерфейса `async_parallel_search`
- `def search_multiple_books(self, isbns: List[str], **kwargs) -> Dict[str, Any]`
  - Эмуляция старого интерфейса `search_multiple_books`

### 2. DualWriteCacheManager

Менеджер dual-write для записи в старые и новые кэши.

**Расположение:** `scraper_core/integration/dual_write.py`

**Основные методы:**
- `async def write_isbn_data(self, isbn: str, data: Dict[str, Any])`
  - Запись данных ISBN в оба кэша
- `async def read_isbn_data(self, isbn: str) -> Optional[Dict[str, Any]]`
  - Чтение данных ISBN (приоритет новому кэшу)
- `async def migrate_old_cache(self)`
  - Миграция данных из старого кэша в новый

### 3. SelectorIntegration

Интеграция с системой селекторов из `debug_selectors.py`.

**Расположение:** `scraper_core/integration/selector_integration.py`

**Основные методы:**
- `def integrate_selectors(resource_id: str) -> Dict[str, Any]`
  - Интеграция селекторов для ресурса
- `def generate_selector_config(test_data: Dict[str, Any]) -> Dict[str, Any]`
  - Генерация конфигурации селекторов на основе тестовых данных

## Система метрик

### MetricsCollector

**Расположение:** `scraper_core/metrics/collector.py`

**Основные методы:**
- `def record_scraping_time(resource_id: str, time_ms: float)`
  - Запись времени скрапинга
- `def record_success(resource_id: str)`
  - Запись успешного выполнения
- `def record_failure(resource_id: str, error: str)`
  - Запись ошибки
- `def get_metrics_summary() -> Dict[str, Any]`
  - Получение сводки метрик

## Примеры использования

### Базовый пример

```python
import asyncio
from scraper_core.orchestrator.core import ScraperOrchestrator

async def main():
    # Инициализация оркестратора
    orchestrator = ScraperOrchestrator(
        config_dir="config",
        max_concurrent_tasks=3,
        use_search_coordinator=True,
        use_tab_manager=True
    )
    
    # Список ISBN для обработки
    isbns = ["9785171204408", "9785171204415", "9785171204422"]
    
    # Выполнение скрапинга
    results = await orchestrator.scrape_isbns(isbns)
    
    # Вывод результатов
    print(f"Обработано ISBN: {len(results['processed'])}")
    print(f"Успешно: {results['stats']['successful']}")
    print(f"Ошибки: {results['stats']['failed']}")
    
    # Корректное завершение
    await orchestrator.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

### Использование отдельных компонентов

```python
import asyncio
from scraper_core.orchestrator.search import SearchCoordinator
from scraper_core.orchestrator.retry import RetryHandler
from scraper_core.handlers.factory import ResourceHandlerFactory

async def scrape_with_retry(isbn: str, resource_id: str):
    # Инициализация компонентов
    search_coordinator = SearchCoordinator()
    retry_handler = RetryHandler(max_retries=3, backoff_factor=2.0)
    
    # Получение обработчика ресурса
    handler = ResourceHandlerFactory.create_handler(resource_id)
    
    # Выполнение с повторными попытками
    async def scrape_func():
        return await handler.scrape(isbn)
    
    try:
        result = await retry_handler.execute_with_retry(scrape_func)
        return result
    except Exception as e:
        print(f"Ошибка при скрапинге {isbn}: {e}")
        return None
```

### Конфигурация через JSON

```json
// config/scraper_config.json
{
  "max_concurrent_tasks": 5,
  "enable_auto_generation": true,
  "default_timeout": 30,
  "cache_ttl": 3600,
  "resources": ["labirint", "book24", "chitai-gorod"]
}

// config/resources_config.json
{
  "labirint": {
    "type": "web",
    "base_url": "https://www.labirint.ru",
    "selectors": {
      "title": ".prodtitle",
      "author": ".authors",
      "price": ".buying-price-val-number"
    },
    "timeout": 30
  }
}
```

## Расширение архитектуры

### Создание нового обработчика ресурсов

```python
from scraper_core.handlers.base import BaseResourceHandler
from scraper_core.handlers.factory import register_handler

class CustomResourceHandler(BaseResourceHandler):
    """Пользовательский обработчик ресурса."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Инициализация
    
    async def scrape(self, isbn: str) -> Dict[str, Any]:
        # Реализация логики скрапинга
        pass
    
    async def validate_response(self, response: Any) -> bool:
        # Валидация ответа
        pass
    
    async def extract_data(self, response: Any) -> Dict[str, Any]:
        # Извлечение данных
        pass

# Регистрация обработчика
register_handler("custom", CustomResourceHandler)
```

### Добавление новой стратегии AntiBotHandler

```python
from scraper_core.orchestrator.antibot import AntiBotHandlerInterface

class AdvancedAntiBotHandler(AntiBotHandlerInterface):
    """Продвинутый обработчик анти-бот защиты."""
    
    async def apply_protection(self, driver: Any, resource_id: str):
        # Применение дополнительных защитных мер
        await self.rotate_user_agent(driver)
        await self.add_random_delay()
    
    def detect_blocking(self, response: Any) -> bool:
        # Детектирование блокировок
        return "blocked" in response.text.lower()
    
    async def handle_blocking(self, driver: Any, resource_id: str):
        # Обработка блокировок
        await self.switch_proxy(driver)
        await asyncio.sleep(60)  # Ожидание перед повторной попыткой
```

## Логирование и отладка

Архитектура использует стандартный модуль logging Python. Уровень логирования можно настроить через конфигурацию:

```python
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Логирование в компонентах
logger = logging.getLogger(__name__)
logger.info("Запуск оркестратора")
```

## Обработка ошибок

Все компоненты архитектуры используют исключения для обработки ошибок:

- `ScrapingError` - базовое исключение для ошибок скрапинга
- `ResourceUnavailableError` - ресурс недоступен
- `SelectorNotFoundError` - селектор не найден
- `TimeoutError` - таймаут операции

## Производительность и оптимизация

### Рекомендации по настройке:

1. **Количество одновременных задач**: Зависит от ресурсов системы и ограничений целевых сайтов
2. **Размер пула вкладок**: Оптимально 3-5 вкладок на ресурс
3. **Таймауты**: Настраивать в зависимости от скорости ответа ресурсов
4. **Кэширование**: Использовать кэширование селекторов и результатов

### Мониторинг производительности:

```python
# Получение метрик
metrics = orchestrator.get_metrics()
print(f"Среднее время обработки: {metrics['avg_processing_time']}ms")
print(f"Успешность: {metrics['success_rate']}%")
print(f"Использование ресурсов: {metrics['resource_utilization']}")
```

## Заключение

Новая архитектура предоставляет гибкую, расширяемую и надежную систему для скрапинга данных о книгах. Модульная структура позволяет легко добавлять новые ресурсы, обработчики и стратегии оптимизации.

Для получения дополнительной информации смотрите:
- [MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md) - руководство по