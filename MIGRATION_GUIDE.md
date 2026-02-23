# Руководство по миграции на новую архитектуру

## Обзор

Эта документация описывает переход от старой архитектуры скрапинга к новой модульной системе, основанной на оркестраторе, конфигурационных файлах JSON и обработчиках ресурсов.

## Что было сделано

### 1. Новая архитектура пакетов
```
scraper_core/
├── config/           # Конфигурационная система (Pydantic модели, загрузчики)
├── handlers/         # Обработчики ресурсов (веб, API, JSON-LD, таблицы)
├── integration/      # Интеграция с существующим кодом
├── isbn/            # Обработка ISBN (валидация, нормализация)
├── orchestrator/     # Оркестратор скрапинга (управление задачами)
├── parsers/         # Парсеры (интеграция debug_selectors и html_fragment)
└── utils/           # Вспомогательные утилиты
```

### 2. Ключевые компоненты

#### Оркестратор (`scraper_core/orchestrator/core.py`)
- Управление параллельными задачами скрапинга
- Автоматическое обновление селекторов на основе результатов
- Интеграция всех компонентов системы

#### Компоненты оркестрационного слоя (реализованы в Итерациях A и B)

**SearchCoordinator** (`scraper_core/orchestrator/search.py`)
- Координация поиска между ресурсами
- Приоритизация ресурсов на основе статистики успешности
- Балансировка нагрузки между ресурсами

**LinkCollector** (`scraper_core/orchestrator/links.py`)
- Сбор и валидация ссылок из HTML-контента
- Фильтрация дубликатов и нерелевантных URL
- Интеграция с WebResourceHandler

**TabManager** (`scraper_core/orchestrator/tabs.py`)
- Управление вкладками браузера для параллельного скрапинга
- Балансировка нагрузки между вкладками
- Мониторинг состояния вкладок

**RetryHandler** (`scraper_core/orchestrator/retry.py`)
- Обработка ошибок с экспоненциальным backoff
- Стратегии обработки различных типов ошибок
- Интеграция с WebResourceHandler и TabManager

**DriverManager** (`scraper_core/orchestrator/drivers.py`)
- Централизованное управление драйверами (Selenium/Playwright)
- Пул драйверов для переиспользования
- Механизмы очистки и пересоздания драйверов

**AntiBotHandler** (`scraper_core/orchestrator/antibot.py`)
- Стратегии обхода блокировок
- Поддержка прокси и ротации user-agent
- Обнаружение и обработка блокировок

**TaskQueue** (`scraper_core/orchestrator/queue.py`)
- Система очередей задач с поддержкой приоритетов
- Интерфейсы для простой и приоритетной очередей
- Интеграция с SearchCoordinator

#### Обработчики ресурсов
- **WebResourceHandler**: Веб-скрапинг через Selenium/requests
- **ApiResourceHandler**: Работа с REST API
- **JsonLdResourceHandler**: Парсинг структурированных данных JSON-LD
- **TableResourceHandler**: Обработка табличных данных

#### Конфигурационная система
- JSON-конфиги для тестовых данных и селекторов
- Pydantic модели для валидации
- Автоматическая генерация конфигураций

#### Интеграция с debug_selectors
- Полная замена hardcoded селекторов из `resources.py`
- Автоматическая генерация селекторов на основе тестовых данных
- Совместимость с существующим функционалом `debug_selectors.py`

## Миграция существующего кода

### 1. Обновленный `scraper.py`
- Сохранена обратная совместимость со старым API
- Все основные функции (`async_parallel_search`, `search_multiple_books` и т.д.) теперь используют новую архитектуру
- Старые классы (`RussianBookScraperUC`) помечены как устаревшие, но сохранены для совместимости

### 2. Использование новой архитектуры

#### Вариант 1: Прямое использование оркестратора
```python
from scraper_core.orchestrator.core import ScraperOrchestrator

orchestrator = ScraperOrchestrator(config_dir="config")
results = await orchestrator.scrape_isbns(["9781234567890", "9789876543210"])
```

#### Вариант 2: Использование через адаптер (для совместимости)
```python
from scraper_core.orchestrator.legacy_adapter import LegacyScraperAdapter

adapter = LegacyScraperAdapter()
results = await adapter.async_parallel_search(["9781234567890"])
```

#### Вариант 3: Использование обновленного `scraper.py` (рекомендуется)
```python
from scraper import async_parallel_search, search_multiple_books

# Асинхронный вариант
results = await async_parallel_search(["9781234567890"])

# Синхронный вариант
results = search_multiple_books(["9781234567890"])
```

#### Вариант 4: Использование отдельных компонентов оркестрационного слоя
```python
from scraper_core.orchestrator.search import SearchCoordinator
from scraper_core.orchestrator.tabs import TabManager
from scraper_core.orchestrator.retry import RetryHandler
from scraper_core.handlers.factory import ResourceHandlerFactory

# Инициализация компонентов
search_coordinator = SearchCoordinator()
tab_manager = TabManager(max_tabs=3)
retry_handler = RetryHandler(max_retries=3)

# Получение ресурса для обработки ISBN
isbn = "9785171204408"
resource_id = await search_coordinator.get_next_resource(isbn)

if resource_id:
    # Получение обработчика ресурса
    handler = ResourceHandlerFactory.create_handler(resource_id)
    
    # Получение вкладки для скрапинга
    tab = await tab_manager.acquire_tab(resource_id)
    
    try:
        # Выполнение скрапинга с повторными попытками
        async def scrape_task():
            return await handler.scrape(isbn, tab=tab)
        
        result = await retry_handler.execute_with_retry(scrape_task)
        print(f"Результат: {result}")
    finally:
        # Освобождение вкладки
        await tab_manager.release_tab(tab)
```

#### Вариант 5: Расширенная конфигурация оркестратора
```python
from scraper_core.orchestrator.core import ScraperOrchestrator
from scraper_core.orchestrator.retry import RetryConfig
from scraper_core.orchestrator.drivers import DriverConfig
from scraper_core.orchestrator.antibot import AntiBotConfig

# Расширенная конфигурация компонентов
retry_config = RetryConfig(
    max_retries=3,
    backoff_factor=2.0,
    retryable_errors=["TimeoutError", "ConnectionError"]
)

driver_config = DriverConfig(
    driver_type="selenium",
    headless=True,
    implicit_wait=10
)

antibot_config = AntiBotConfig(
    enable_proxy_rotation=False,
    random_delay_range=(1, 3)
)

# Создание оркестратора с расширенными настройками
orchestrator = ScraperOrchestrator(
    config_dir="config",
    max_concurrent_tasks=5,
    use_search_coordinator=True,
    use_tab_manager=True,
    use_retry_handler=True,
    use_driver_manager=True,
    use_antibot_handler=True,
    use_priority_queue=True,
    retry_config=retry_config,
    driver_config=driver_config,
    antibot_config=antibot_config,
    max_tabs=3
)
```

### 3. Конфигурационные файлы

#### Основные конфиги
- `config/scraper_config.json`: Настройки окружения скрапера
- `config/resources_config.json`: Конфигурации ресурсов (Читай-город, Book.ru, РГБ)

#### Конфигурация компонентов оркестрационного слоя

**Настройка SearchCoordinator:**
```json
{
  "search_coordinator": {
    "enable_priority_routing": true,
    "resource_weights": {
      "labirint": 1.0,
      "book24": 0.8,
      "chitai-gorod": 0.7
    },
    "failure_decay_factor": 0.9
  }
}
```

**Настройка TabManager:**
```json
{
  "tab_manager": {
    "max_tabs_per_resource": 3,
    "tab_timeout_seconds": 30,
    "enable_tab_reuse": true
  }
}
```

**Настройка RetryHandler:**
```json
{
  "retry_handler": {
    "max_retries": 3,
    "backoff_factor": 2.0,
    "max_backoff_seconds": 60,
    "retryable_errors": ["TimeoutError", "ConnectionError"]
  }
}
```

**Настройка AntiBotHandler:**
```json
{
  "antibot_handler": {
    "enable_proxy_rotation": false,
    "user_agents": [
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    ],
    "random_delay_range": [1, 3]
  }
}
```

#### Миграция существующих данных
```python
from scraper import migrate_to_new_architecture

# Автоматическая миграция селекторов из resources.py
migration_results = migrate_to_new_architecture("config")
print(f"Мигрировано селекторов: {migration_results}")
```

## Преимущества новой архитектуры

### 1. Модульность
- Каждый компонент выполняет одну четкую задачу
- Легко добавлять новые типы ресурсов
- Простое тестирование отдельных компонентов

### 2. Конфигурируемость
- Все настройки в JSON-файлах
- Динамическое обновление селекторов
- Поддержка разных типов ресурсов через конфигурацию

### 3. Расширяемость
- Легко добавлять новые обработчики ресурсов
- Поддержка различных источников данных (веб, API, JSON-LD, таблицы)
- Гибкая система оркестрации задач

### 4. Совместимость
- Полная обратная совместимость с существующим кодом
- Постепенная миграция без breaking changes
- Сохранение старого API для существующих интеграций

## Тестирование

### Существующие тесты
```bash
# Тесты конфигурационной системы
pytest tests/test_config_system.py -v

# Тесты интеграции селекторов
pytest tests/test_selector_integration.py -v

# Тесты оркестратора (частично проходят, требуют доработки моков)
pytest tests/test_orchestrator_integration.py -v
```

### Тесты новых компонентов оркестрационного слоя
```bash
# Тесты SearchCoordinator
pytest tests/test_search_coordinator.py -v

# Тесты LinkCollector
pytest tests/test_link_collector.py -v

# Тесты TabManager
pytest tests/test_tab_manager.py -v

# Тесты RetryHandler
pytest tests/test_retry_handler.py -v

# Тесты DriverManager
pytest tests/test_driver_manager.py -v

# Тесты AntiBotHandler
pytest tests/test_antibot_handler.py -v

# Тесты TaskQueue
pytest tests/test_task_queue.py -v
```

### Новые тесты
- Создана комплексная тестовая система с моками
- Тестирование всех компонентов изолированно
- Интеграционные тесты для проверки совместимости
- Тесты производительности и надежности новых компонентов

## Следующие шаги

### 1. Полная миграция ресурсов
- Завершить миграцию всех трех ресурсов (Читай-город, Book.ru, РГБ)
- Обновить конфигурационные файлы с реальными данными
- Протестировать на реальных ISBN

### 2. Оптимизация производительности
- Настройка пулов соединений
- Кэширование результатов
- Оптимизация параллельных запросов

### 3. Дополнительные функции
- Мониторинг и логирование
- Метрики производительности
- Веб-интерфейс для управления конфигурацией

### 4. Документация
- Детальная документация API
- Примеры использования
- Руководство по расширению системы

## Важные замечания

### Сохраненные файлы
- `scraper_original_backup.py`: Резервная копия оригинального `scraper.py`
- `TODO_old.md`: Старый файл задач (для истории)

### Обратная совместимость
- Все существующие вызовы `scraper.py` продолжают работать
- Старые классы и функции помечены как deprecated
- Рекомендуется постепенно переходить на новый API

### Конфигурация по умолчанию
- Созданы базовые конфигурационные файлы
- Можно дополнить реальными тестовыми данными
- Автоматическая генерация при отсутствии конфигов

## Заключение

Новая архитектура предоставляет:
1. **Гибкость**: Легко настраивается под разные ресурсы
2. **Масштабируемость**: Поддержка параллельной обработки
3. **Поддерживаемость**: Четкое разделение ответственности
4. **Совместимость**: Плавный переход от старой системы

Рекомендуется начать использование с обновленного `scraper.py`, который предоставляет тот же API, но использует новую архитектуру под капотом.