# RetryHandler API

## Обзор

`RetryHandler` — компонент для обработки ошибок с повторными попытками, экспоненциальным backoff и circuit breaker. Интегрируется с `WebResourceHandler`, `TabManager` и `ScraperOrchestrator` для повышения надежности системы скрапинга.

## Основные возможности

1. **Экспоненциальный backoff** с настраиваемыми параметрами
2. **Классификация ошибок** (сетевые, ресурсные, парсинг, валидация)
3. **Circuit breaker** для предотвращения запросов к неработающим ресурсам
4. **Category-specific конфигурация** — разные настройки для разных типов ошибок
5. **Статистика выполнения** — мониторинг успешных/неудачных попыток

## Импорт

```python
from scraper_core.orchestrator.retry import (
    RetryHandler,
    RetryConfig,
    ErrorCategory,
    CircuitBreaker,
    RetryStats
)
```

## Конфигурация

### RetryConfig

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `max_retries` | `int` | 3 | Максимальное количество повторных попыток |
| `base_delay` | `float` | 1.0 | Базовая задержка в секундах |
| `max_delay` | `float` | 60.0 | Максимальная задержка в секундах |
| `jitter` | `float` | 0.1 | Случайное отклонение задержки (0.0-1.0) |
| `exponential_base` | `float` | 2.0 | Основание для экспоненциального backoff |
| `retry_network` | `bool` | `True` | Повторять при сетевых ошибках |
| `retry_resource` | `bool` | `True` | Повторять при ошибках ресурса |
| `retry_parsing` | `bool` | `False` | Повторять при ошибках парсинга |
| `retry_validation` | `bool` | `False` | Повторять при ошибках валидации |
| `retry_unknown` | `bool` | `True` | Повторять при неизвестных ошибках |
| `timeout` | `Optional[float]` | `None` | Таймаут для операции |
| `circuit_breaker_threshold` | `int` | 5 | Порог для circuit breaker |
| `circuit_breaker_reset_time` | `float` | 60.0 | Время сброса circuit breaker |
| `category_specific_config` | `Dict[ErrorCategory, Dict]` | См. ниже | Конфигурация для разных категорий ошибок |

### Category-specific конфигурация

По умолчанию:
```python
{
    ErrorCategory.NETWORK: {"max_retries": 5, "base_delay": 2.0},
    ErrorCategory.RESOURCE: {"max_retries": 3, "base_delay": 3.0},
    ErrorCategory.PARSING: {"max_retries": 1, "base_delay": 1.0},
    ErrorCategory.VALIDATION: {"max_retries": 1, "base_delay": 1.0},
    ErrorCategory.UNKNOWN: {"max_retries": 2, "base_delay": 1.5},
}
```

## Использование

### Базовое использование

```python
# Создание обработчика с конфигурацией по умолчанию
retry_handler = RetryHandler()

# Создание с пользовательской конфигурацией
config = RetryConfig(
    max_retries=5,
    base_delay=2.0,
    retry_parsing=True
)
retry_handler = RetryHandler(config)
```

### Выполнение функции с повторными попытками

```python
async def fetch_data(url: str) -> str:
    # Ваша логика получения данных
    response = await aiohttp.get(url)
    return await response.text()

# Использование RetryHandler
try:
    result = await retry_handler.execute_with_retry(
        fetch_data,
        resource_id="my_resource",
        "https://example.com"
    )
except Exception as e:
    print(f"Все попытки завершились неудачей: {e}")
```

### Синхронные функции

```python
def sync_function(x: int, y: int) -> int:
    return x + y

result = await retry_handler.execute_sync_with_retry(
    sync_function,
    resource_id="calc",
    10, 20
)
```

## Интеграция с WebResourceHandler

`RetryHandler` автоматически интегрируется с `WebResourceHandler` через фабрику обработчиков:

```python
from scraper_core.handlers.factory import ResourceHandlerFactory

# Создание RetryHandler
retry_handler = RetryHandler()

# Создание WebResourceHandler с RetryHandler
handler = ResourceHandlerFactory.create_handler(
    resource_config,
    retry_handler=retry_handler
)
```

## Интеграция с ScraperOrchestrator

`ScraperOrchestrator` автоматически создает и использует `RetryHandler` при инициализации:

```python
from scraper_core.orchestrator.core import ScraperOrchestrator

# Создание оркестратора с RetryHandler
orchestrator = ScraperOrchestrator(
    use_retry_handler=True,
    retry_config=RetryConfig(max_retries=5)
)

# RetryHandler будет автоматически использоваться для всех операций скрапинга
```

## Circuit Breaker

`RetryHandler` включает встроенный circuit breaker для каждого ресурса:

```python
# Получение circuit breaker для ресурса
cb = retry_handler.get_circuit_breaker("resource_id")

# Проверка состояния
if cb.is_open():
    print("Circuit breaker открыт - ресурс временно недоступен")

# Принудительный сброс
retry_handler.reset_circuit_breaker("resource_id")
```

## Статистика

```python
# Получение статистики
stats = retry_handler.get_stats()
print(f"Попытки: {stats.attempts}")
print(f"Успехи: {stats.successes}")
print(f"Неудачи: {stats.failures}")
print(f"Общая задержка: {stats.total_delay}")

# Сброс статистики
retry_handler.reset_stats()
```

## Категории ошибок

`ErrorCategory` определяет типы ошибок для стратегий повторных попыток:

- `NETWORK` — сетевые ошибки (таймауты, проблемы соединения)
- `RESOURCE` — ошибки ресурса (404, 503, блокировки)
- `PARSING` — ошибки парсинга (неверный формат данных)
- `VALIDATION` — ошибки валидации (некорректные данные)
- `UNKNOWN` — неизвестные ошибки

## Примеры

### Полный пример использования

```python
import asyncio
from scraper_core.orchestrator.retry import RetryHandler, RetryConfig

async def main():
    # Конфигурация
    config = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        retry_network=True,
        retry_resource=True
    )
    
    # Создание обработчика
    retry_handler = RetryHandler(config)
    
    # Функция, которая может падать
    call_count = 0
    async def unstable_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Сетевая ошибка")
        return "Успех!"
    
    # Выполнение с повторными попытками
    try:
        result = await retry_handler.execute_with_retry(
            unstable_function,
            resource_id="test"
        )
        print(f"Результат: {result}")
    except Exception as e:
        print(f"Ошибка: {e}")
    
    # Вывод статистики
    stats = retry_handler.get_stats()
    print(f"Статистика: {stats}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Интеграция с существующей системой

```python
from scraper_core.orchestrator.core import ScraperOrchestrator
from scraper_core.orchestrator.retry import RetryConfig

# Создание оркестратора с расширенной обработкой ошибок
orchestrator = ScraperOrchestrator(
    config_dir="config",
    use_retry_handler=True,
    use_tab_manager=True,
    retry_config=RetryConfig(
        max_retries=5,
        base_delay=2.0,
        category_specific_config={
            ErrorCategory.NETWORK: {"max_retries": 10, "base_delay": 3.0},
            ErrorCategory.RESOURCE: {"max_retries": 3, "base_delay": 5.0},
        }
    )
)

# Запуск скрапинга - все ошибки будут обрабатываться автоматически
results = await orchestrator.scrape_isbns(["9781234567890"])
```

## Тестирование

Unit-тесты находятся в `tests/test_retry_handler.py`. Запуск тестов:

```bash
pytest tests/test_retry_handler.py -v
```

## Примечания

1. **Минимальная задержка**: 0.1 секунды (даже если расчетная задержка меньше)
2. **Джиттер**: Добавляет случайность для предотвращения синхронизации запросов
3. **Circuit breaker**: Автоматически открывается после нескольких ошибок и закрывается после таймаута
4. **Статистика**: Накопительная для всего времени работы обработчика
5. **Потокобезопасность**: Обработчик предназначен для использования в асинхронном контексте

## Ссылки

- [ScraperOrchestrator API](../scraper_core/orchestrator/core.py)
- [WebResourceHandler API](../scraper_core/handlers/web_handler.py)
- [TabManager API](../scraper_core/orchestrator/tabs.py)