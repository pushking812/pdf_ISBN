# Примеры использования компонентов оркестрационного слоя

Этот каталог содержит практические примеры использования компонентов новой архитектуры скрапинга, реализованных в Итерациях A, B и C проекта.

## Содержание

1. [Обзор](#обзор)
2. [Запуск примеров](#запуск-примеров)
3. [Список примеров](#список-примеров)
4. [Использование в реальных проектах](#использование-в-реальных-проектах)
5. [Дополнительные ресурсы](#дополнительные-ресурсы)

## Обзор

Новая архитектура скрапинга включает следующие ключевые компоненты:

- **ScraperOrchestrator** - центральный координатор системы
- **SearchCoordinator** - оптимизация выбора ресурсов
- **TabManager** - управление вкладками браузера
- **RetryHandler** - обработка ошибок с экспоненциальным backoff
- **DriverManager** - централизованное управление драйверами
- **AntiBotHandler** - стратегии обхода блокировок
- **LinkCollector** - сбор и валидация ссылок
- **LegacyAdapter** - обратная совместимость со старым кодом
- **DualWriteCacheManager** - миграция данных между кэшами

## Запуск примеров

### Предварительные требования

1. Установите зависимости проекта:
   ```bash
   pip install -r requirements.txt
   ```

2. Убедитесь, что у вас есть конфигурационные файлы в директории `config/`:
   - `config/scraper_config.json`
   - `config/resources_config.json`

### Запуск всех примеров

```bash
cd examples
python component_usage_examples.py
```

### Запуск конкретного примера

Вы можете модифицировать файл `component_usage_examples.py`, чтобы запускать только определенные примеры:

```python
# В конце файла замените:
# asyncio.run(main())
# на:
asyncio.run(example_search_coordinator())
```

## Список примеров

### 1. SearchCoordinator
**Файл:** `component_usage_examples.py` - функция `example_search_coordinator()`

**Описание:** Демонстрирует использование SearchCoordinator для оптимизации выбора ресурсов на основе статистики успешности.

**Ключевые моменты:**
- Обновление статистики ресурсов
- Выбор наиболее подходящего ресурса для ISBN
- Расчет приоритетов ресурсов

### 2. TabManager
**Функция:** `example_tab_manager()`

**Описание:** Показывает управление вкладками браузера для параллельного скрапинга.

**Ключевые моменты:**
- Создание пула вкладок
- Балансировка нагрузки между вкладками
- Мониторинг состояния вкладок

### 3. RetryHandler
**Функция:** `example_retry_handler()`

**Описание:** Демонстрирует обработку ошибок с экспоненциальным backoff.

**Ключевые моменты:**
- Настройка параметров повторных попыток
- Автоматический повтор неудачных операций
- Обработка различных типов ошибок

### 4. DriverManager
**Функция:** `example_driver_manager()`

**Описание:** Показывает централизованное управление драйверами Selenium/Playwright.

**Ключевые моменты:**
- Создание пула драйверов
- Конфигурация параметров драйверов
- Переиспользование драйверов

### 5. AntiBotHandler
**Функция:** `example_antibot_handler()`

**Описание:** Демонстрирует стратегии обхода анти-бот защиты.

**Ключевые моменты:**
- Ротация User-Agent
- Обнаружение блокировок
- Настройка случайных задержек

### 6. LinkCollector
**Функция:** `example_link_collector()`

**Описание:** Показывает сбор и валидацию ссылок из HTML-контента.

**Ключевые моменты:**
- Извлечение ссылок из HTML
- Фильтрация дубликатов
- Валидация URL

### 7. Полный ScraperOrchestrator
**Функция:** `example_full_orchestrator()`

**Описание:** Демонстрирует интеграцию всех компонентов в единую систему.

**Ключевые моменты:**
- Конфигурация всех компонентов
- Создание оркестратора с расширенными настройками
- Управление параллельными задачами

### 8. LegacyAdapter
**Функция:** `example_legacy_adapter()`

**Описание:** Показывает обеспечение обратной совместимости со старым кодом.

**Ключевые моменты:**
- Совместимость со старым API `scraper.py`
- Поддержка существующих интеграций
- Постепенная миграция

### 9. DualWriteCacheManager
**Функция:** `example_dual_write_cache()`

**Описание:** Демонстрирует миграцию данных между старыми и новыми кэшами.

**Ключевые моменты:**
- Одновременная запись в оба кэша
- Чтение с приоритетом нового кэша
- Миграция существующих данных

## Использование в реальных проектах

### Базовый пример использования оркестратора

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

## Дополнительные ресурсы

1. **Документация API:** [`../docs/architecture_api.md`](../docs/architecture_api.md) - полная документация по API новой архитектуры
2. **Руководство по миграции:** [`../MIGRATION_GUIDE.md`](../MIGRATION_GUIDE.md) - руководство по переходу на новую архитектуру
3. **Архитектурная документация:** [`../CONCEPTION.md`](../CONCEPTION.md) - общая архитектура проекта
4. **Тесты:** [`../tests/`](../tests/) - тесты для всех компонентов

## Примечания

- Примеры используют моки и имитацию для демонстрационных целей
- Для реального использования необходимо настроить конфигурационные файлы
- Некоторые примеры требуют установки дополнительных зависимостей (Selenium, Playwright)
- Рекомендуется запускать тесты перед использованием в production

## Лицензия

Примеры распространяются под той же лицензией, что и основной проект.