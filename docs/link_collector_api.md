# LinkCollector API документация

## Обзор

`LinkCollector` - компонент оркестрационного слоя, отвечающий за извлечение, валидацию и кеширование ссылок на продукты со страниц поиска. Компонент интегрирован с `WebResourceHandler` для загрузки страниц и использует конфигурацию ресурсов для определения селекторов ссылок.

## Назначение

1. **Извлечение ссылок**: Поиск ссылок на продукты на страницах поиска с использованием CSS-селекторов, определенных в конфигурации ресурса.
2. **Валидация URL**: Преобразование относительных URL в абсолютные, проверка корректности URL.
3. **Фильтрация дубликатов**: Удаление повторяющихся ссылок.
4. **Кеширование**: Сохранение результатов поиска ссылок для повышения производительности при повторных запросах.
5. **Интеграция с WebResourceHandler**: Использование существующей инфраструктуры загрузки страниц.

## Импорт

```python
from scraper_core.orchestrator.links import LinkCollector
```

## Класс LinkCollector

### Конструктор

```python
def __init__(self, cache_ttl_seconds: int = 3600)
```

**Параметры:**
- `cache_ttl_seconds` (int, optional): Время жизни записей в кеше в секундах. По умолчанию 3600 (1 час).

**Пример:**
```python
collector = LinkCollector(cache_ttl_seconds=1800)  # Кеш на 30 минут
```

### Основные методы

#### `collect_links`

```python
async def collect_links(
    self,
    isbn: str,
    resource_config: Dict[str, Any],
    web_handler: Any
) -> List[str]
```

Основной метод для сбора ссылок на продукты.

**Параметры:**
- `isbn` (str): ISBN книги для поиска.
- `resource_config` (Dict[str, Any]): Конфигурация ресурса, содержащая:
  - `id` (str): Идентификатор ресурса.
  - `search_url_template` (str): Шаблон URL для поиска с placeholder `{isbn}`.
  - `product_link_selectors` (List[str]): Список CSS-селекторов для поиска ссылок на продукты.
  - `no_product_phrases` (List[str], optional): Фразы, указывающие на отсутствие результатов.
- `web_handler` (Any): Экземпляр `WebResourceHandler` для загрузки страниц.

**Возвращает:**
- `List[str]`: Список найденных и валидированных URL продуктов.

**Пример:**
```python
links = await collector.collect_links(
    "9781234567890",
    {
        "id": "book-ru",
        "search_url_template": "https://book.ru/search?q={isbn}",
        "product_link_selectors": [".product-link", "a[href*='/book/']"],
        "no_product_phrases": ["Ничего не найдено"]
    },
    web_handler
)
```

#### `clear_cache`

```python
async def clear_cache(self)
```

Полная очистка кеша ссылок и истории просмотренных URL.

**Пример:**
```python
await collector.clear_cache()
```

#### `get_stats`

```python
def get_stats(self) -> Dict[str, Any]
```

Получение статистики работы сборщика ссылок.

**Возвращает:**
- `Dict[str, Any]`: Словарь со статистикой:
  - `cache_size` (int): Количество записей в кеше.
  - `seen_urls_count` (int): Количество уникальных URL, обработанных сборщиком.
  - `cache_hit_rate` (float): Коэффициент попаданий в кеш (0.0-1.0).

**Пример:**
```python
stats = collector.get_stats()
print(f"Размер кеша: {stats['cache_size']}")
```

### Внутренние методы (protected)

#### `_normalize_url`

```python
def _normalize_url(self, url: str, base_url: str) -> str
```

Нормализация URL: преобразование относительного URL в абсолютный.

**Параметры:**
- `url` (str): URL для нормализации.
- `base_url` (str): Базовый URL для разрешения относительных путей.

**Возвращает:**
- `str`: Нормализованный абсолютный URL.

#### `_is_valid_url`

```python
def _is_valid_url(self, url: str) -> bool
```

Проверка валидности URL.

**Параметры:**
- `url` (str): URL для проверки.

**Возвращает:**
- `bool`: `True` если URL валиден, иначе `False`.

#### `_filter_and_validate_links`

```python
def _filter_and_validate_links(
    self,
    links: List[str],
    base_url: str
) -> List[str]
```

Фильтрация дубликатов и валидация списка ссылок.

**Параметры:**
- `links` (List[str]): Список сырых ссылок.
- `base_url` (str): Базовый URL для нормализации.

**Возвращает:**
- `List[str]`: Список уникальных валидных ссылок.

## Интеграция с WebResourceHandler

### Требования к WebResourceHandler

Для работы с `LinkCollector` класс `WebResourceHandler` должен реализовывать метод:

```python
async def fetch_page(self, url: str) -> Optional[str]
```

Метод должен загружать страницу по указанному URL и возвращать её HTML содержимое или `None` в случае ошибки.

### Пример интеграции

```python
from scraper_core.handlers.web_handler import WebResourceHandler
from scraper_core.orchestrator.links import LinkCollector

# Создание обработчика ресурса
resource_config = {
    "id": "test-resource",
    "search_url_template": "https://example.com/search?q={isbn}",
    "product_link_selectors": [".product-link"],
    "use_selenium": False
}
web_handler = WebResourceHandler(resource_config)

# Создание сборщика ссылок
link_collector = LinkCollector()

# Сбор ссылок
links = await link_collector.collect_links(
    "9781234567890",
    resource_config,
    web_handler
)

print(f"Найдено ссылок: {len(links)}")
for link in links:
    print(f"  - {link}")
```

## Конфигурация

### Параметры ресурса для LinkCollector

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `id` | str | Да | Уникальный идентификатор ресурса |
| `search_url_template` | str | Да | Шаблон URL для поиска с placeholder `{isbn}` |
| `product_link_selectors` | List[str] | Да | CSS-селекторы для поиска ссылок на продукты |
| `no_product_phrases` | List[str] | Нет | Фразы, указывающие на отсутствие результатов на странице |

### Пример конфигурации ресурса

```json
{
  "id": "book-ru",
  "name": "Book.ru",
  "search_url_template": "https://book.ru/search?q={isbn}",
  "product_link_selectors": [
    "a[data-test-id='bookCardLink']",
    "a[href*='/book/']"
  ],
  "no_product_phrases": [
    "По вашему запросу ничего не найдено",
    "Товар не найден"
  ]
}
```

## Обработка ошибок

### Типичные сценарии ошибок

1. **Отсутствие шаблона URL**: Если `search_url_template` отсутствует или пуст, метод `collect_links` вернет пустой список и залогирует ошибку.
2. **Ошибка загрузки страницы**: Если `web_handler.fetch_page` возвращает `None` или возникает исключение, метод вернет пустой список.
3. **Отсутствие селекторов**: Если `product_link_selectors` пуст, метод вернет пустой список и залогирует предупреждение.
4. **Страница "ничего не найдено"**: Если на странице обнаружены фразы из `no_product_phrases`, метод вернет пустой список.

### Логирование

`LinkCollector` использует стандартный логгер Python с именем `scraper_core.orchestrator.links`. Уровень логирования можно настроить через конфигурацию логирования приложения.

## Примеры использования

### Базовый пример

```python
import asyncio
from scraper_core.handlers.web_handler import WebResourceHandler
from scraper_core.orchestrator.links import LinkCollector

async def main():
    # Конфигурация ресурса
    resource_config = {
        "id": "chitai-gorod",
        "search_url_template": "https://www.chitai-gorod.ru/search?phrase={isbn}",
        "product_link_selectors": ['a[href^="/product/"]'],
        "no_product_phrases": ["Ничего не найдено"],
        "use_selenium": False
    }
    
    # Инициализация компонентов
    web_handler = WebResourceHandler(resource_config)
    link_collector = LinkCollector(cache_ttl_seconds=1800)
    
    # Сбор ссылок для нескольких ISBN
    isbns = ["9785171202444", "9785171477957"]
    
    for isbn in isbns:
        print(f"Поиск ссылок для ISBN: {isbn}")
        links = await link_collector.collect_links(isbn, resource_config, web_handler)
        
        if links:
            print(f"  Найдено {len(links)} ссылок:")
            for link in links:
                print(f"    - {link}")
        else:
            print("  Ссылки не найдены")
    
    # Получение статистики
    stats = link_collector.get_stats()
    print(f"\nСтатистика: {stats}")
    
    # Очистка кеша
    await link_collector.clear_cache()

if __name__ == "__main__":
    asyncio.run(main())
```

### Интеграция с SearchCoordinator

```python
from scraper_core.orchestrator.search import SearchCoordinator
from scraper_core.orchestrator.links import LinkCollector
from scraper_core.handlers.web_handler import WebResourceHandler

class IntegratedScraper:
    def __init__(self):
        self.search_coordinator = SearchCoordinator()
        self.link_collector = LinkCollector()
        self.web_handlers = {}
    
    async def process_isbn(self, isbn: str):
        # Получение оптимального ресурса от SearchCoordinator
        resource_config = self.search_coordinator.get_next_resource(isbn)
        resource_id = resource_config["id"]
        
        # Получение или создание WebResourceHandler
        if resource_id not in self.web_handlers:
            self.web_handlers[resource_id] = WebResourceHandler(resource_config)
        
        web_handler = self.web_handlers[resource_id]
        
        # Сбор ссылок
        links = await self.link_collector.collect_links(
            isbn, resource_config, web_handler
        )
        
        # Обновление статистики SearchCoordinator
        if links:
            self.search_coordinator.record_success(resource_id)
        else:
            self.search_coordinator.record_failure(resource_id)
        
        return links
```

## Тестирование

### Unit-тесты

Для `LinkCollector` доступны unit-тесты в файле `tests/test_link_collector.py`. Тесты покрывают:

1. Инициализацию и базовые методы
2. Нормализацию и валидацию URL
3. Извлечение ссылок из HTML
4. Фильтрацию и валидацию ссылок
5. Работу кеша
6. Интеграцию с WebResourceHandler

### Запуск тестов

```bash
pytest tests/test_link_collector.py -v
```

## Производительность

### Кеширование

`LinkCollector` использует двухуровневое кеширование:

1. **Кеш ссылок**: Сохраняет результаты поиска для пар (ISBN, ресурс) с TTL.
2. **Множество просмотренных URL**: Предотвращает обработку дубликатов в рамках одной сессии.

### Рекомендации по настройке

1. **TTL кеша**: Установите `cache_ttl_seconds` в соответствии с частотой обновления данных на целевых ресурсах.
2. **Селекторы**: Используйте специфичные CSS-селекторы для уменьшения ложных срабатываний.
3. **Параллелизм**: `LinkCollector` является потокобезопасным и может использоваться в асинхронных контекстах.

## Совместимость

### Версии Python
- Python 3.8+
- Требуется поддержка async/await

### Зависимости
- `beautifulsoup4` (для парсинга HTML)
- `aiohttp` (для HTTP-запросов, если не используется Selenium)
- `undetected-chromedriver` (для Selenium-режима)

## История изменений

### Версия 1.0.0 (2026-02-22)
- Первоначальная реализация `LinkCollector`
- Интеграция с `WebResourceHandler`
- Поддержка кеширования и валидации URL
- Полный набор unit-тестов

## Ссылки

- [SearchCoordinator API](search_coordinator_api.md)
- [WebResourceHandler API](web_resource_handler_api.md)
- [Конфигурация ресурсов](../config/resources_config.json)
- [Примеры использования](../examples/)