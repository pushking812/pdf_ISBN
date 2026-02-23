# Схема JSON-конфигурации для тестовых данных и селекторов

## Общая структура

```json
{
  "version": "1.0.0",
  "last_updated": "2026-02-22T19:47:00Z",
  "resources": {
    "resource_id": {
      "metadata": {...},
      "search_config": {...},
      "test_data": [...],
      "selectors": {...},
      "settings": {...}
    }
  }
}
```

## Детальная схема

### 1. Метаданные ресурса
```json
{
  "metadata": {
    "name": "Читай-город",
    "base_url": "https://www.chitai-gorod.ru",
    "description": "Книжный интернет-магазин",
    "enabled": true,
    "priority": 1
  }
}
```

### 2. Конфигурация поиска
```json
{
  "search_config": {
    "search_url": "https://www.chitai-gorod.ru/search",
    "search_method": "GET",
    "search_params": {
      "q": "{isbn}",
      "sort": "relevance"
    },
    "search_selectors": {
      "result_links": "css:.product-card a.product-card__link",
      "next_page": "css:.pagination__next",
      "no_results": "css:.search-empty"
    },
    "result_validation": {
      "min_links": 1,
      "max_links": 10,
      "timeout_seconds": 30
    }
  }
}
```

### 3. Тестовые данные
```json
{
  "test_data": [
    {
      "id": "chitai-gorod-001",
      "url": "https://www.chitai-gorod.ru/product/123456",
      "html_snippet": "<div class=\"product\">...</div>",
      "fields": {
        "title": {
          "value": "Мастер и Маргарита",
          "type": "text",
          "required": true,
          "validation": "non_empty"
        },
        "author": {
          "value": "Михаил Булгаков",
          "type": "text",
          "required": true,
          "validation": "non_empty"
        },
        "pages": {
          "value": "480",
          "type": "numeric",
          "required": false,
          "validation": "positive_integer"
        },
        "year": {
          "value": "2020",
          "type": "numeric",
          "required": false,
          "validation": "year_range:1900-2026"
        },
        "price": {
          "value": "899 руб.",
          "type": "price",
          "required": false,
          "validation": "price_format"
        }
      },
      "metadata": {
        "collected_at": "2026-02-20T10:30:00Z",
        "isbn": "9785171125953",
        "verified": true
      }
    }
  ]
}
```

### 4. Селекторы (сгенерированные и ручные)
```json
{
  "selectors": {
    "title": {
      "patterns": [
        {
          "type": "css",
          "value": ".product-title",
          "confidence": 0.95,
          "generated_at": "2026-02-21T14:30:00Z",
          "test_cases_passed": 5,
          "test_cases_failed": 0
        },
        {
          "type": "xpath", 
          "value": "//h1[@class='product-title']",
          "confidence": 0.92,
          "generated_at": "2026-02-21T14:31:00Z",
          "test_cases_passed": 5,
          "test_cases_failed": 0
        },
        {
          "type": "css",
          "value": "h1.title",
          "confidence": 0.88,
          "generated_at": "2026-02-21T14:32:00Z",
          "test_cases_passed": 4,
          "test_cases_failed": 1
        }
      ],
      "fallback_strategy": "try_all_until_success",
      "required": true
    },
    "author": {
      "patterns": [...],
      "fallback_strategy": "try_all_until_success",
      "required": true
    }
  }
}
```

### 5. Настройки ресурса
```json
{
  "settings": {
    "scraping": {
      "delay_range": [1.0, 3.0],
      "max_tabs": 3,
      "timeout_seconds": 30,
      "headless": false,
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    },
    "retry": {
      "max_attempts": 3,
      "backoff_factor": 2.0,
      "retry_on_status": [429, 500, 502, 503, 504],
      "blocked_detection_patterns": ["Доступ ограничен", "captcha", "403"]
    },
    "validation": {
      "min_confidence": 0.7,
      "required_fields": ["title", "author"],
      "field_validators": {
        "title": "non_empty",
        "author": "non_empty", 
        "pages": "positive_integer",
        "year": "year_range:1900-2026"
      }
    }
  }
}
```

## Пример полного конфига для Читай-города

```json
{
  "version": "1.0.0",
  "last_updated": "2026-02-22T19:47:00Z",
  "resources": {
    "chitai-gorod": {
      "metadata": {
        "name": "Читай-город",
        "base_url": "https://www.chitai-gorod.ru",
        "description": "Книжный интернет-магазин",
        "enabled": true,
        "priority": 1
      },
      "search_config": {
        "search_url": "https://www.chitai-gorod.ru/search",
        "search_method": "GET",
        "search_params": {"q": "{isbn}"},
        "search_selectors": {
          "result_links": "css:.product-card a.product-card__link",
          "next_page": "css:.pagination__next",
          "no_results": "css:.search-empty"
        }
      },
      "test_data": [
        {
          "id": "chitai-001",
          "url": "https://www.chitai-gorod.ru/product/123456",
          "fields": {
            "title": "Мастер и Маргарита",
            "author": "Михаил Булгаков",
            "pages": "480",
            "year": "2020"
          }
        }
      ],
      "selectors": {
        "title": {
          "patterns": [
            {"type": "css", "value": ".product-title", "confidence": 0.95},
            {"type": "xpath", "value": "//h1[@class='product-title']", "confidence": 0.92}
          ]
        },
        "author": {
          "patterns": [
            {"type": "css", "value": ".product-author a", "confidence": 0.93},
            {"type": "xpath", "value": "//div[@class='author']/a", "confidence": 0.90}
          ]
        }
      },
      "settings": {
        "scraping": {
          "delay_range": [1.0, 3.0],
          "max_tabs": 3,
          "timeout_seconds": 30
        },
        "retry": {
          "max_attempts": 3,
          "backoff_factor": 2.0
        }
      }
    }
  }
}
```

## Миграция текущих тестовых данных

### Из `debug_selectors.py`:
```python
# Текущие тестовые данные в get_test_data_to_parse()
test_data = {
    "chitai-gorod": [
        {
            "url": "https://www.chitai-gorod.ru/product/...",
            "title": "...",
            "author": "...",
            "pages": "...",
            "year": "..."
        }
    ]
}
```

### В JSON-формат:
```json
{
  "chitai-gorod": {
    "test_data": [
      {
        "url": "https://www.chitai-gorod.ru/product/...",
        "fields": {
          "title": "...",
          "author": "...", 
          "pages": "...",
          "year": "..."
        }
      }
    ]
  }
}
```

## Утилиты для работы с конфигом

### 1. Валидация схемы
```python
def validate_config_schema(config: dict) -> bool:
    """Проверяет соответствие JSON-конфига схеме"""
    # Проверка обязательных полей
    # Проверка типов данных
    # Проверка значений
```

### 2. Загрузка и кэширование
```python
class ConfigLoader:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._config = None
        self._last_modified = None
    
    def load(self) -> dict:
        """Загружает конфиг с кэшированием"""
        # Проверка изменения файла
        # Загрузка и парсинг JSON
        # Валидация схемы
```

### 3. Обновление селекторов
```python
class SelectorUpdater:
    def update_selectors(self, resource_id: str, field: str, new_patterns: list):
        """Обновляет селекторы в конфиге"""
        # Загрузка текущего конфига
        # Обновление patterns для указанного поля
        # Пересчет confidence на основе тестов
        # Сохранение обновленного конфига
```

### 4. Генерация конфига из текущих данных
```python
def generate_config_from_current():
    """Генерирует начальный JSON-конфиг из текущих тестовых данных"""
    # Извлечение тестовых данных из debug_selectors.py
    # Извлечение селекторов из resources.py
    # Создание структуры JSON
    # Сохранение в файл
```

## Преимущества JSON-конфигурации

1. **Единый источник истины**: Все селекторы и тестовые данные в одном месте
2. **Версионирование**: Легко отслеживать изменения селекторов
3. **Горячее обновление**: Можно обновлять конфиг без перезапуска приложения
4. **Тестирование**: Легко добавлять новые тестовые случаи
5. **Отладка**: Прозрачность того, какие селекторы используются и с какой уверенностью

## Следующие шаги

1. Создать скрипт для миграции текущих данных в JSON-формат
2. Реализовать загрузчик конфигурации
3. Обновить `debug_selectors.py` для работы с JSON-конфигом
4. Создать инструменты для валидации и обновления конфига