# Интерфейсная архитектура для универсального парсинга

## Основная концепция

Создаем систему плагинов, где каждый тип ресурса реализует общий интерфейс `ResourceHandler`. Это позволяет:
1. Единообразно работать с разными типами ресурсов (веб-сайты, API, JSON-LD, таблицы)
2. Учитывать специфические требования (ChromeDriver, асинхронные запросы)
3. Легко добавлять новые типы ресурсов
4. Интегрировать существующие API клиенты

## Базовый интерфейс

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from selenium.webdriver.remote.webdriver import WebDriver

class ResourceHandler(ABC):
    """Базовый интерфейс для обработки ресурсов"""
    
    @abstractmethod
    async def search_books(self, isbn: str) -> List[Dict[str, Any]]:
        """Поиск книг по ISBN, возвращает список ссылок на страницы книг"""
        pass
    
    @abstractmethod
    async def parse_book_page(self, url: str) -> Dict[str, Any]:
        """Парсинг страницы книги, возвращает данные о книге"""
        pass
    
    @abstractmethod
    def requires_driver(self) -> bool:
        """Требуется ли ChromeDriver для работы этого обработчика"""
        return False
    
    @abstractmethod
    def get_resource_id(self) -> str:
        """Идентификатор ресурса (chitai-gorod, book-ru, rsl, google-books)"""
        pass
```

## Реализации интерфейса

### 1. WebResourceHandler (для сайтов с HTML)
```python
class WebResourceHandler(ResourceHandler):
    """Обработчик веб-сайтов с использованием debug_selectors"""
    
    def __init__(self, config: Dict[str, Any], selector_client: SelectorClient):
        self.config = config
        self.selector_client = selector_client
        self.driver = None
    
    def requires_driver(self) -> bool:
        # Определяем по конфигу: некоторые сайты требуют Selenium
        return self.config.get('settings', {}).get('requires_selenium', False)
    
    async def search_books(self, isbn: str) -> List[Dict[str, Any]]:
        # Используем search_url из конфига
        search_url = self._build_search_url(isbn)
        
        if self.requires_driver():
            # Используем ChromeDriver для динамических страниц
            return await self._search_with_driver(search_url)
        else:
            # Используем requests для статических страниц
            return await self._search_with_requests(search_url)
    
    async def parse_book_page(self, url: str) -> Dict[str, Any]:
        # Используем SelectorClient для парсинга через debug_selectors
        return await self.selector_client.parse_book_page(url, self.get_resource_id())
```

### 2. ApiResourceHandler (для API ресурсов)
```python
class ApiResourceHandler(ResourceHandler):
    """Обработчик API ресурсов (Google Books, Open Library)"""
    
    def __init__(self, config: Dict[str, Any], api_client: Any):
        self.config = config
        self.api_client = api_client
    
    def requires_driver(self) -> bool:
        return False  # API не требует ChromeDriver
    
    async def search_books(self, isbn: str) -> List[Dict[str, Any]]:
        # Для API поиск и парсинг объединены
        book_data = await self.api_client.get_book_data(isbn)
        return [{"url": f"api:{self.get_resource_id()}:{isbn}", "data": book_data}]
    
    async def parse_book_page(self, url: str) -> Dict[str, Any]:
        # Для API данные уже получены при поиске
        # URL формата: api:google-books:9785171125953
        _, resource_id, isbn = url.split(":")
        return await self.api_client.get_book_data(isbn)
```

### 3. JsonLdResourceHandler (специализация для Book.ru)
```python
class JsonLdResourceHandler(WebResourceHandler):
    """Обработчик для сайтов с JSON-LD данными (Book.ru)"""
    
    async def parse_book_page(self, url: str) -> Dict[str, Any]:
        # Сначала пытаемся извлечь JSON-LD
        json_ld_data = await self._extract_json_ld(url)
        if json_ld_data:
            return self._parse_json_ld(json_ld_data)
        
        # Fallback на стандартный парсинг через debug_selectors
        return await super().parse_book_page(url)
    
    async def _extract_json_ld(self, url: str) -> Optional[Dict]:
        # Извлечение JSON-LD из <script type="application/ld+json">
        pass
```

### 4. TableResourceHandler (специализация для РГБ)
```python
class TableResourceHandler(WebResourceHandler):
    """Обработчик для сайтов с табличными данными (РГБ)"""
    
    async def parse_book_page(self, url: str) -> Dict[str, Any]:
        # Используем универсальный table parser
        table_data = await self._extract_table_data(url)
        if table_data:
            return self._parse_table(table_data)
        
        # Fallback на стандартный парсинг
        return await super().parse_book_page(url)
```

## Фабрика обработчиков

```python
class ResourceHandlerFactory:
    """Создает обработчики ресурсов на основе конфигурации"""
    
    def __init__(self, config_loader: ConfigLoader, selector_client: SelectorClient):
        self.config_loader = config_loader
        self.selector_client = selector_client
        self.api_clients = self._init_api_clients()
    
    def create_handler(self, resource_id: str) -> ResourceHandler:
        config = self.config_loader.get_resource_config(resource_id)
        resource_type = config.get('metadata', {}).get('type', 'web')
        
        if resource_type == 'api':
            api_client = self.api_clients.get(resource_id)
            if not api_client:
                raise ValueError(f"API client not found for {resource_id}")
            return ApiResourceHandler(config, api_client)
        
        elif resource_type == 'json_ld':
            return JsonLdResourceHandler(config, self.selector_client)
        
        elif resource_type == 'table':
            return TableResourceHandler(config, self.selector_client)
        
        else:  # web по умолчанию
            return WebResourceHandler(config, self.selector_client)
    
    def _init_api_clients(self) -> Dict[str, Any]:
        """Инициализация API клиентов из api_clients.py"""
        clients = {}
        
        # Google Books API
        clients['google-books'] = GoogleBooksApiClient()
        
        # Open Library API  
        clients['open-library'] = OpenLibraryApiClient()
        
        # Другие API клиенты
        return clients
```

## Интеграция с существующим кодом

### 1. API клиенты (`api_clients.py`)
```python
# Адаптируем под интерфейс ApiClient
class GoogleBooksApiClient:
    async def get_book_data(self, isbn: str) -> Dict[str, Any]:
        # Используем существующую функцию get_from_google_books_async
        async with aiohttp.ClientSession() as session:
            return await get_from_google_books_async(session, isbn)

class OpenLibraryApiClient:
    async def get_book_data(self, isbn: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            return await get_from_open_library_async(session, isbn)
```

### 2. JSON-конфигурация с типами ресурсов
```json
{
  "resources": {
    "chitai-gorod": {
      "metadata": {
        "type": "web",
        "requires_selenium": true,
        "name": "Читай-город"
      }
    },
    "book-ru": {
      "metadata": {
        "type": "json_ld", 
        "requires_selenium": false,
        "name": "Book.ru"
      }
    },
    "rsl": {
      "metadata": {
        "type": "table",
        "requires_selenium": true,
        "name": "РГБ"
      }
    },
    "google-books": {
      "metadata": {
        "type": "api",
        "name": "Google Books API"
      }
    }
  }
}
```

### 3. Обновленный SelectorClient
```python
class SelectorClient:
    """Клиент для парсинга с поддержкой разных типов ресурсов"""
    
    def __init__(self, handler_factory: ResourceHandlerFactory):
        self.handler_factory = handler_factory
        self.handlers = {}  # Кэш обработчиков по resource_id
    
    async def parse_book_page(self, url: str, resource_id: str) -> Dict[str, Any]:
        # Получаем или создаем обработчик
        if resource_id not in self.handlers:
            self.handlers[resource_id] = self.handler_factory.create_handler(resource_id)
        
        handler = self.handlers[resource_id]
        return await handler.parse_book_page(url)
    
    def get_handler(self, resource_id: str) -> ResourceHandler:
        """Возвращает обработчик для оркестратора"""
        if resource_id not in self.handlers:
            self.handlers[resource_id] = self.handler_factory.create_handler(resource_id)
        return self.handlers[resource_id]
```

## Оркестратор с поддержкой разных типов ресурсов

```python
class ScraperOrchestrator:
    """Оркестратор, работающий с любыми типами ресурсов"""
    
    async def process_isbns(self, isbns: List[str]) -> List[Dict]:
        results = []
        
        for resource_id in self.config_loader.get_all_resource_ids():
            handler = self.selector_client.get_handler(resource_id)
            
            if handler.requires_driver():
                # Обработка через TabManager с ChromeDriver
                resource_results = await self._process_with_driver(handler, isbns)
            else:
                # Обработка без драйвера (API или статические страницы)
                resource_results = await self._process_without_driver(handler, isbns)
            
            results.extend(resource_results)
        
        return results
    
    async def _process_with_driver(self, handler: ResourceHandler, isbns: List[str]):
        """Обработка ресурсов, требующих ChromeDriver"""
        # Используем TabManager для параллельной обработки
        tab_manager = TabManager(max_tabs=3)
        return await tab_manager.process_resource(handler, isbns)
    
    async def _process_without_driver(self, handler: ResourceHandler, isbns: List[str]):
        """Обработка ресурсов без ChromeDriver (API, статические страницы)"""
        tasks = []
        for isbn in isbns:
            task = handler.search_books(isbn)
            tasks.append(task)
        
        # Параллельная обработка через asyncio
        search_results = await asyncio.gather(*tasks)
        
        # Парсинг найденных страниц
        parsed_results = []
        for result in search_results:
            for book_link in result:
                book_data = await handler.parse_book_page(book_link['url'])
                parsed_results.append(book_data)
        
        return parsed_results
```

## Преимущества архитектуры

1. **Единый интерфейс**: Все ресурсы обрабатываются через `ResourceHandler`
2. **Гибкость**: Легко добавлять новые типы ресурсов
3. **Интеграция**: Существующие API клиенты работают через адаптеры
4. **Оптимизация**: Ресурсы без ChromeDriver обрабатываются параллельно
5. **Конфигурируемость**: Тип ресурса и требования определяются в JSON

## Этапы реализации

### Этап 1: Базовые интерфейсы
1. Создать `ResourceHandler` ABC
2. Реализовать `WebResourceHandler` с `SelectorClient`
3. Создать `ResourceHandlerFactory`

### Этап 2: Специализированные обработчики
1. Реализовать `JsonLdResourceHandler` для Book.ru
2. Реализовать `TableResourceHandler` для РГБ
3. Создать адаптеры для API клиентов

### Этап 3: Интеграция
1. Обновить `SelectorClient` для работы с фабрикой
2. Модифицировать `ScraperOrchestrator` для поддержки разных типов
3. Создать JSON-конфиги с типами ресурсов

### Этап 4: Миграция
1. Перенести тестовые данные в JSON-конфиги
2. Заменить вызовы `resources.py` на фабрику обработчиков
3. Протестировать все типы ресурсов

Эта архитектура полностью соответствует вашим требованиям: универсальный интерфейс, учет разных типов ресурсов, интеграция с API клиентами, конфигурируемость через JSON.