# Обновленная архитектура с учетом замечаний

## Учет ключевых моментов

### 1. ISBN обработка из `pdf_extract_isbn.py`
- **Функции валидации**: `validate_isbn10()`, `validate_isbn13()`
- **Поиск в тексте**: `find_isbn_in_text()` с нормализацией символов
- **Нормализация**: `replace_similar_digits()` в `utils.py`

**Решение**: Создать модуль `core/isbn_utils.py`:
```python
# core/isbn_utils.py
from typing import Optional

def normalize_isbn(isbn: str) -> str:
    """Нормализация ISBN (удаление дефисов, пробелов)"""
    
def validate_isbn(isbn: str) -> bool:
    """Валидация ISBN-10 или ISBN-13"""
    
def extract_isbn_from_text(text: str, strict: bool = True) -> Optional[str]:
    """Извлечение ISBN из текста (адаптация find_isbn_in_text)"""
```

### 2. Конфигурация `ScraperConfig` из `config.py`
Класс содержит:
- Настройки ChromeDriver (headless, timeouts)
- Задержки и стратегии ожидания
- Фразы для обнаружения блокировок
- Параметры параллелизма

**Решение**: Трехуровневая конфигурация:
1. **`ScraperConfig`** (существующий) - для обратной совместимости
2. **`ScraperEnvConfig`** (новый) - настройки среды из JSON
3. **`ResourceConfig`** (новый) - конфигурация ресурсов из JSON

### 3. Структура модулей (небольшие, вложенные пакеты)
```
scraper_core/           # Основной пакет
├── __init__.py
├── config/             # Конфигурация
│   ├── __init__.py
│   ├── base.py         # Базовые классы конфигов
│   ├── env_config.py   # ScraperEnvConfig
│   ├── resource_config.py
│   └── loader.py       # ConfigLoader
├── isbn/               # Обработка ISBN
│   ├── __init__.py
│   ├── utils.py        # Функции валидации
│   ├── processor.py    # ISBNProcessor
│   └── normalizer.py   # Нормализация
├── handlers/           # Обработчики ресурсов
│   ├── __init__.py
│   ├── base.py         # ResourceHandler интерфейс
│   ├── web.py          # WebResourceHandler
│   ├── api.py          # ApiResourceHandler
│   ├── jsonld.py       # JsonLdResourceHandler
│   ├── table.py        # TableResourceHandler
│   └── factory.py      # ResourceHandlerFactory
├── orchestrator/       # Оркестрационный слой
│   ├── __init__.py
│   ├── core.py         # ScraperOrchestrator
│   ├── search.py       # SearchCoordinator
│   ├── links.py        # LinkCollector
│   ├── tabs.py         # TabManager
│   ├── queue.py        # TaskQueue
│   └── retry.py        # RetryHandler
├── parsers/            # Парсеры
│   ├── __init__.py
│   ├── selector.py     # SelectorClient (адаптер debug_selectors)
│   ├── jsonld.py       # JsonLdParser
│   ├── table.py        # TableParser
│   └── html.py         # HTML анализ (адаптация html_fragment)
├── utils/              # Утилиты
│   ├── __init__.py
│   ├── metrics.py      # MetricsCollector
│   ├── anti_bot.py     # AntiBotHandler
│   ├── cache.py        # Кэширование
│   └── logging.py      # Настройка логирования
└── drivers/            # Управление драйверами
    ├── __init__.py
    ├── manager.py      # DriverManager
    └── config.py       # Настройки ChromeDriver
```

## Обновленный план итераций

### Итерация 1: Базовая инфраструктура и конфигурация
**Цель**: Создать структуру пакетов и систему конфигурации.

#### Подзадачи:
- [ ] **1.1.1**: Создать структуру пакетов `scraper_core/`
- [ ] **1.1.2**: Вынести функции ISBN в `core/isbn/utils.py`
- [ ] **1.1.3**: Создать `ScraperEnvConfig` (наследник `ScraperConfig`)
- [ ] **1.1.4**: Создать `ResourceConfig` для JSON-конфига ресурсов
- [ ] **1.1.5**: Реализовать `ConfigLoader` с поддержкой обоих конфигов
- [ ] **1.1.6**: Создать схемы валидации JSON (Pydantic)
- [ ] **1.1.7**: Написать тесты для конфигурации
- [ ] **1.2.1**: Создать `scraper_config.json` (настройки среды)
- [ ] **1.2.2**: Создать `resources_config.json` (ресурсы)
- [ ] **1.2.3**: Скрипт миграции тестовых данных из `debug_selectors.py`
- [ ] **1.3.1**: Интеграция с существующим `ScraperConfig`
- [ ] **1.3.2**: Проверка обратной совместимости

#### Выходные артефакты:
- Структура пакетов `scraper_core/`
- Рабочая система конфигурации (JSON + Python классы)
- Мигрированные тестовые данные
- Обратная совместимость с `ScraperConfig`

### Итерация 2: Базовые обработчики и парсеры
**Цель**: Создать ResourceHandler и адаптеры для существующего кода.

#### Подзадачи:
- [ ] **2.1.1**: Создать `ResourceHandler` интерфейс
- [ ] **2.1.2**: Реализовать `WebResourceHandler` с адаптацией `debug_selectors`
- [ ] **2.1.3**: Создать `SelectorClient` как адаптер для `debug_selectors.py`
- [ ] **2.1.4**: Адаптировать `api_clients.py` под `ApiResourceHandler`
- [ ] **2.1.5**: Создать `ResourceHandlerFactory`
- [ ] **2.2.1**: Вынести функции из `html_fragment.py` в `parsers/html.py`
- [ ] **2.2.2**: Создать адаптер для обратной совместимости `html_fragment.py`
- [ ] **2.2.3**: Протестировать парсинг на тестовых данных
- [ ] **2.3.1**: Интеграция с существующим `scraper.py` через адаптер
- [ ] **2.3.2**: Проверка работы всех типов ресурсов

### Итерация 3: Оркестрационный слой (часть 1)
**Цель**: Создать основные компоненты оркестрации.

#### Подзадачи:
- [ ] **3.1.1**: Реализовать `ISBNProcessor` с использованием `isbn_utils`
- [ ] **3.1.2**: Создать `SearchCoordinator` для координации поиска
- [ ] **3.1.3**: Реализовать `LinkCollector` с балансировкой
- [ ] **3.1.4**: Создать `TaskQueue` с приоритетами ресурсов
- [ ] **3.2.1**: Реализовать `DriverManager` для управления ChromeDriver
- [ ] **3.2.2**: Интеграция настроек из `ScraperEnvConfig`
- [ ] **3.2.3**: Создать `AntiBotHandler` с базовыми стратегиями
- [ ] **3.3.1**: Протестировать оркестрацию без парсинга
- [ ] **3.3.2**: Проверить балансировку нагрузки

### Итерация 4: Оркестрационный слой (часть 2) и специализированные парсеры
**Цель**: Завершить оркестрационный слой и добавить специализированные парсеры.

#### Подзадачи:
- [ ] **4.1.1**: Создать `TabManager` на основе `async_parallel_search`
- [ ] **4.1.2**: Реализовать `RetryHandler` с экспоненциальным backoff
- [ ] **4.1.3**: Создать `ScraperOrchestrator` как точку входа
- [ ] **4.2.1**: Реализовать `JsonLdParser` для Book.ru
- [ ] **4.2.2**: Создать `TableParser` для РГБ
- [ ] **4.2.3**: Добавить автоматическое определение типа контента
- [ ] **4.3.1**: Интеграция всех компонентов
- [ ] **4.3.2**: Тестирование полного цикла

### Итерация 5: Интеграция и миграция
**Цель**: Интегрировать с существующим кодом и начать миграцию.

#### Подзадачи:
- [ ] **5.1.1**: Создать адаптер для `main.py`
- [ ] **5.1.2**: Реализовать dual-write в старые кэши
- [ ] **5.1.3**: Миграция `isbn_data_cache.json`
- [ ] **5.1.4**: Миграция `pdf_isbn_cache.json`
- [ ] **5.2.1**: A/B тестирование новой и старой системы
- [ ] **5.2.2**: Сбор метрик производительности
- [ ] **5.2.3**: Оптимизация на основе метрик
- [ ] **5.3.1**: Документация API
- [ ] **5.3.2**: Руководство по миграции

### Итерация 6: Оптимизация и production-готовность
**Цель**: Оптимизация, мониторинг, подготовка к production.

#### Подзадачи:
- [ ] **6.1.1**: Оптимизация кэширования селекторов
- [ ] **6.1.2**: Реализация предзагрузки драйверов
- [ ] **6.1.3**: Настройка ротации User-Agent и прокси
- [ ] **6.2.1**: Создание `MetricsCollector` с дашбордом
- [ ] **6.2.2**: Настройка алертинга
- [ ] **6.2.3**: Создание скриптов развертывания
- [ ] **6.3.1**: Нагрузочное тестирование
- [ ] **6.3.2**: Тестирование отказоустойчивости
- [ ] **6.3.3**: Финальная документация

## Конфигурационные файлы

### `scraper_config.json` (настройки среды):
```json
{
  "version": "1.0.0",
  "driver": {
    "headless": false,
    "window_size": "1920,1080",
    "user_agent": "Mozilla/5.0...",
    "page_load_timeout": 30,
    "page_load_strategy": "eager"
  },
  "scraping": {
    "max_concurrent_tabs": 3,
    "delay_range": [1.0, 3.0],
    "retry_attempts": 3,
    "retry_backoff_factor": 2.0
  },
  "anti_bot": {
    "enabled": true,
    "user_agent_rotation": true,
    "proxy_enabled": false,
    "blockage_phrases": ["DDoS-Guard", "Checking your browser"]
  },
  "logging": {
    "level": "INFO",
    "file": "scraper.log",
    "metrics_enabled": true
  }
}
```

### `resources_config.json` (ресурсы):
```json
{
  "version": "1.0.0",
  "resources": {
    "chitai-gorod": {
      "type": "web",
      "metadata": {"name": "Читай-город", "enabled": true},
      "search": {
        "url": "https://www.chitai-gorod.ru/search",
        "params": {"q": "{isbn}"},
        "requires_selenium": true
      },
      "test_data": [...],
      "selectors": {...}
    },
    "book-ru": {
      "type": "json_ld",
      "metadata": {"name": "Book.ru", "enabled": true},
      "search": {...}
    }
  }
}
```

## Интеграция с существующим кодом

### 1. `ScraperConfig` совместимость:
```python
# config.py остается без изменений для обратной совместимости
# Новый код использует ScraperEnvConfig

class ScraperEnvConfig(ScraperConfig):
    """Расширенный конфиг с поддержкой JSON"""
    def __init__(self, config_path: str = "scraper_config.json"):
        # Загрузка из JSON
        # Вызов super() с параметрами из JSON
```

### 2. `debug_selectors.py` интеграция:
```python
# parsers/selector.py
class SelectorClient:
    """Адаптер для debug_selectors.py"""
    def __init__(self, config: ScraperEnvConfig):
        self.config = config
        # Использует функции из debug_selectors с новым конфигом
```

### 3. `main.py` адаптер:
```python
# Сохраняем старый интерфейс
def main():
    # Если флаг --new-system, используем ScraperOrchestrator
    # Иначе используем старый scraper.py
```

## Преимущества подхода

1. **Постепенная миграция**: Старый код продолжает работать
2. **Модульность**: Небольшие, специализированные модули
3. **Конфигурируемость**: JSON + Python классы
4. **Расширяемость**: Легко добавлять новые типы ресурсов
5. **Совместимость**: Интеграция с существующим кодом

Начинаем с **Итерации 1**: создание структуры пакетов и системы конфигурации.