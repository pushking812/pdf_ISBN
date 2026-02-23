# План рефакторинга scraper.py в оркестрационный слой

## Текущее состояние scraper.py

### Основные функции:
1. `parse_book_page_for_resource()` - парсинг страницы с использованием жестких селекторов
2. `async_parallel_search()` - асинхронный поиск с управлением вкладками
3. `RussianBookScraperUC` - синхронный скрапер для Читай-города
4. `process_isbn_async()` - обработка одного ISBN
5. `run_api_stage()` - API-стадия обработки

### Проблемы текущей архитектуры:
1. **Смешение ответственности**: Парсинг и оркестрация в одном модуле
2. **Жесткие зависимости**: Прямое использование селекторов из `resources.py`
3. **Отсутствие абстракций**: Нет четкого разделения между поиском, сбором ссылок и парсингом
4. **Сложность расширения**: Добавление нового ресурса требует изменений в нескольких местах

## Новая архитектура оркестрационного слоя

### Модульная структура:
```
scraper_orchestrator.py     # Главный оркестратор
├── isbn_processor.py       # Обработка ISBN
├── search_coordinator.py   # Координация поиска
├── link_collector.py       # Сбор ссылок
├── tab_manager.py          # Управление вкладками
├── task_queue.py           # Очередь задач
├── retry_handler.py        # Обработка повторов
└── selector_client.py      # Клиент для debug_selectors
```

### 1. Главный оркестратор (`scraper_orchestrator.py`)

```python
class ScraperOrchestrator:
    """Главный оркестратор процесса скрапинга"""
    
    def __init__(self, config_path: str):
        self.config = ConfigLoader(config_path).load()
        self.isbn_processor = ISBNProcessor()
        self.search_coordinator = SearchCoordinator(self.config)
        self.link_collector = LinkCollector()
        self.tab_manager = TabManager(self.config)
        self.task_queue = TaskQueue()
        self.retry_handler = RetryHandler(self.config)
        self.selector_client = SelectorClient()
    
    async def process_isbns(self, isbns: List[str]) -> List[Dict]:
        """Основной процесс обработки списка ISBN"""
        # 1. Нормализация ISBN
        normalized_isbns = self.isbn_processor.normalize(isbns)
        
        # 2. Поиск по всем ресурсам
        search_results = await self.search_coordinator.search_all_resources(normalized_isbns)
        
        # 3. Сбор всех ссылок
        all_links = self.link_collector.collect_links(search_results)
        
        # 4. Формирование пула ссылок с чередованием
        link_pool = self.link_collector.create_balanced_pool(all_links)
        
        # 5. Обработка через пул вкладок
        results = await self.tab_manager.process_link_pool(link_pool, self.selector_client)
        
        return results
```

### 2. Обработчик ISBN (`isbn_processor.py`)

```python
class ISBNProcessor:
    """Обработка и нормализация ISBN"""
    
    def normalize(self, isbns: List[str]) -> List[str]:
        """Нормализует список ISBN (удаляет дефисы, проверяет валидность)"""
        # Использует существующую функцию normalize_isbn из scraper.py
    
    def validate(self, isbn: str) -> bool:
        """Проверяет валидность ISBN"""
    
    def chunk_isbns(self, isbns: List[str], chunk_size: int = 10) -> List[List[str]]:
        """Разбивает ISBN на чанки для параллельной обработки"""
```

### 3. Координатор поиска (`search_coordinator.py`)

```python
class SearchCoordinator:
    """Координация поиска по разным ресурсам"""
    
    async def search_all_resources(self, isbns: List[str]) -> Dict[str, List[SearchResult]]:
        """Выполняет поиск по всем ресурсам для каждого ISBN"""
        results = {}
        
        for resource_id, resource_config in self.config['resources'].items():
            if not resource_config['metadata']['enabled']:
                continue
                
            resource_results = await self._search_resource(resource_id, isbns, resource_config)
            results[resource_id] = resource_results
        
        return results
    
    async def _search_resource(self, resource_id: str, isbns: List[str], config: Dict) -> List[SearchResult]:
        """Поиск на конкретном ресурсе"""
        # Создание драйвера
        # Открытие поисковой страницы
        # Извлечение ссылок на страницы книг
        # Возврат результатов
```

### 4. Сборщик ссылок (`link_collector.py`)

```python
class LinkCollector:
    """Сбор и управление ссылками на страницы книг"""
    
    def collect_links(self, search_results: Dict[str, List[SearchResult]]) -> List[BookLink]:
        """Собирает все ссылки из результатов поиска"""
        links = []
        
        for resource_id, results in search_results.items():
            for result in results:
                for link in result.links:
                    book_link = BookLink(
                        url=link,
                        resource_id=resource_id,
                        isbn=result.isbn,
                        priority=result.priority
                    )
                    links.append(book_link)
        
        return links
    
    def create_balanced_pool(self, links: List[BookLink]) -> List[BookLink]:
        """Создает пул ссылок с чередованием ресурсов"""
        # Группировка по ресурсам
        # Чередование ссылок от разных ресурсов
        # Учет приоритетов ресурсов
```

### 5. Менеджер вкладок (`tab_manager.py`)

```python
class TabManager:
    """Управление пулом вкладок ChromeDriver"""
    
    def __init__(self, config: Dict):
        self.max_tabs = config['settings']['scraping']['max_tabs']
        self.delay_range = config['settings']['scraping']['delay_range']
        self.timeout = config['settings']['scraping']['timeout_seconds']
        self.tabs = []
        self.driver = None
    
    async def process_link_pool(self, link_pool: List[BookLink], selector_client) -> List[Dict]:
        """Обрабатывает пул ссылок через управляемые вкладки"""
        results = []
        
        # Инициализация драйвера
        self.driver = create_chrome_driver()
        
        # Создание вкладок
        for i in range(min(self.max_tabs, len(link_pool))):
            tab = await self._create_tab(i)
            self.tabs.append(tab)
        
        # Распределение задач по вкладкам
        tasks = []
        for i, link in enumerate(link_pool):
            tab_index = i % len(self.tabs)
            task = self._process_link_in_tab(link, self.tabs[tab_index], selector_client)
            tasks.append(task)
        
        # Выполнение задач
        tab_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обработка результатов
        for result in tab_results:
            if isinstance(result, Exception):
                # Обработка ошибок через retry_handler
                continue
            results.append(result)
        
        return results
    
    async def _process_link_in_tab(self, link: BookLink, tab, selector_client) -> Dict:
        """Обрабатывает одну ссылку в указанной вкладке"""
        # Переключение на вкладку
        # Загрузка страницы
        # Передача HTML в selector_client для парсинга
        # Извлечение данных
        # Возврат результата
```

### 6. Очередь задач (`task_queue.py`)

```python
class TaskQueue:
    """Очередь задач с приоритетами и чередованием"""
    
    def __init__(self):
        self.queue = asyncio.PriorityQueue()
        self.resource_counters = {}
    
    async def add_task(self, task: Task, resource_id: str, priority: int = 1):
        """Добавляет задачу в очередь"""
        # Учет количества задач по ресурсам
        # Балансировка нагрузки
    
    async def get_next_task(self) -> Optional[Task]:
        """Возвращает следующую задачу с учетом балансировки"""
        # Чередование задач от разных ресурсов
        # Учет приоритетов
```

### 7. Обработчик повторов (`retry_handler.py`)

```python
class RetryHandler:
    """Обработка блокировок и повторных попыток"""
    
    async def execute_with_retry(self, task_func, max_attempts: int = 3) -> Any:
        """Выполняет функцию с повторными попытками при ошибках"""
        for attempt in range(max_attempts):
            try:
                result = await task_func()
                return result
            except BlockedError as e:
                if attempt < max_attempts - 1:
                    await self._handle_blockage(e, attempt)
                    continue
                raise
            except Exception as e:
                if self._should_retry(e) and attempt < max_attempts - 1:
                    await asyncio.sleep(self.backoff_factor ** attempt)
                    continue
                raise
    
    def _should_retry(self, error: Exception) -> bool:
        """Определяет, нужно ли повторять при данной ошибке"""
        # Проверка по статус-кодам
        # Проверка по тексту ошибки
```

### 8. Клиент для debug_selectors (`selector_client.py`)

```python
class SelectorClient:
    """Клиент для взаимодействия с функционалом debug_selectors"""
    
    def __init__(self, config_path: str):
        self.config_loader = ConfigLoader(config_path)
        self.pattern_cache = {}
    
    async def parse_book_page(self, html: str, resource_id: str, url: str) -> Dict[str, Any]:
        """Парсит страницу книги с использованием селекторов из конфига"""
        # Загрузка конфига ресурса
        config = self.config_loader.get_resource_config(resource_id)
        
        # Проверка наличия селекторов в кэше
        if resource_id not in self.pattern_cache:
            self.pattern_cache[resource_id] = self._load_selectors(config)
        
        # Извлечение данных с использованием селекторов
        result = {}
        selectors = self.pattern_cache[resource_id]
        
        for field, selector_info in selectors.items():
            value = await self._extract_field(html, selector_info, field)
            if value:
                result[field] = value
        
        return result
    
    async def _extract_field(self, html: str, selector_info: Dict, field: str) -> Optional[str]:
        """Извлекает значение поля с использованием лучшего селектора"""
        # Попытка каждого паттерна по порядку confidence
        # Fallback стратегия
        # Валидация извлеченного значения
```

## Миграция существующего кода

### Что сохранить из текущего scraper.py:
1. **`async_parallel_search()`** - логика управления вкладками (переработать)
2. **`TabState` и `TabInfo`** - переработать для новой архитектуры
3. **Логика задержек** - `_random_delay()` (перенести в TabManager)
4. **Обработка модальных окон** - `_handle_city_modal()` (ресурс-специфичная)

### Что удалить/заменить:
1. **`parse_book_page_for_resource()`** - полностью заменить на `SelectorClient`
2. **Жесткие селекторы** - заменить на загрузку из JSON-конфига
3. **`RussianBookScraperUC`** - устаревший синхронный скрапер (можно удалить)
4. **Прямые вызовы `resources.py`** - заменить на `ConfigLoader`

## Этапы рефакторинга

### Этап 1: Создание инфраструктуры
1. Создать `ConfigLoader` для работы с JSON-конфигом
2. Реализовать `SelectorClient` как обертку над `debug_selectors`
3. Создать базовые классы для новой архитектуры

### Этап 2: Рефакторинг поиска
1. Вынести логику поиска в `SearchCoordinator`
2. Реализовать `LinkCollector` для сбора ссылок
3. Создать `TaskQueue` для балансировки нагрузки

### Этап 3: Рефакторинг управления вкладками
1. Переработать `TabManager` на основе `async_parallel_search`
2. Реализовать `RetryHandler` для обработки ошибок
3. Интегрировать `SelectorClient` в процесс парсинга

### Этап 4: Интеграция и тестирование
1. Создать `ScraperOrchestrator` как точку входа
2. Протестировать полный цикл обработки ISBN
3. Сравнить результаты со старой системой

## Преимущества новой архитектуры

1. **Разделение ответственности**: Каждый модуль отвечает за одну задачу
2. **Гибкость**: Легко добавлять новые ресурсы и стратегии
3. **Устойчивость**: Встроенная обработка ошибок и повторных попыток
4. **Масштабируемость**: Балансировка нагрузки между ресурсами
5. **Тестируемость**: Каждый модуль можно тестировать независимо

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| Потеря производительности при добавлении абстракций | Профилирование и оптимизация критических путей |
| Сложность отладки распределенной системы | Детальное логирование, трассировка задач |
| Несовместимость с существующим кодом | Постепенная миграция, сохранение обратной совместимости |
| Увеличение потребления памяти | Мониторинг использования памяти, оптимизация кэшей |

## Следующие шаги

1. Создать детальный план реализации каждого модуля
2. Определить интерфейсы между модулями
3. Создать тестовую среду для проверки новой архитектуры
4. Разработать стратегию постепенной миграции