"""
JSON-схемы для валидации конфигурационных файлов.

Содержит схемы в формате JSON Schema для валидации
scraper_config.json и resources_config.json.
"""

SCHEMA_SCRAPER_CONFIG = {
    "$schema": "http://json-schema.org/draft-2020-12/schema#",
    "title": "Scraper Environment Configuration",
    "description": "Конфигурация окружения скрапера",
    "type": "object",
    "properties": {
        "max_tabs": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
            "default": 3,
            "description": "Максимальное количество вкладок браузера",
        },
        "tab_timeout": {
            "type": "integer",
            "minimum": 10,
            "maximum": 300,
            "default": 60,
            "description": "Таймаут для вкладки (секунды)",
        },
        "headless": {
            "type": "boolean",
            "default": False,
            "description": "Запуск браузера в headless-режиме",
        },
        "user_agent": {
            "type": ["string", "null"],
            "default": None,
            "description": "Пользовательский User-Agent",
        },
        "min_delay": {
            "type": "number",
            "minimum": 0.1,
            "maximum": 10.0,
            "default": 1.0,
            "description": "Минимальная задержка между запросами",
        },
        "max_delay": {
            "type": "number",
            "minimum": 0.1,
            "maximum": 10.0,
            "default": 3.0,
            "description": "Максимальная задержка между запросами",
        },
        "random_delay": {
            "type": "boolean",
            "default": True,
            "description": "Использовать случайные задержки",
        },
        "max_retries": {
            "type": "integer",
            "minimum": 0,
            "maximum": 10,
            "default": 3,
            "description": "Максимальное количество повторных попыток",
        },
        "retry_delay": {
            "type": "number",
            "minimum": 1.0,
            "maximum": 30.0,
            "default": 5.0,
            "description": "Задержка между повторными попытками",
        },
        "log_level": {
            "type": "string",
            "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "default": "INFO",
            "description": "Уровень логирования",
        },
        "verbose": {
            "type": "boolean",
            "default": False,
            "description": "Подробный вывод",
        },
        "config_dir": {
            "type": "string",
            "default": "config",
            "description": "Директория с конфигурационными файлами",
        },
        "cache_dir": {
            "type": "string",
            "default": "cache",
            "description": "Директория для кэша",
        },
        "output_dir": {
            "type": "string",
            "default": "output",
            "description": "Директория для вывода",
        },
        "enable_debug_selectors": {
            "type": "boolean",
            "default": True,
            "description": "Включить интеграцию с debug_selectors",
        },
        "auto_generate_selectors": {
            "type": "boolean",
            "default": True,
            "description": "Автоматически генерировать отсутствующие селекторы",
        },
        "selector_confidence_threshold": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "default": 0.7,
            "description": "Порог уверенности для использования селектора",
        },
        "enabled_resources": {
            "type": "array",
            "items": {"type": "string"},
            "default": ["chitai_gorod", "book_ru", "rsl"],
            "description": "Список включенных ресурсов",
        },
    },
    "additionalProperties": True,
    "required": [],
}

SCHEMA_RESOURCE_CONFIG = {
    "$schema": "http://json-schema.org/draft-2020-12/schema#",
    "title": "Resource Configuration",
    "description": "Конфигурация ресурса для парсинга",
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "description": "Уникальный идентификатор ресурса",
            "pattern": "^[a-z][a-z0-9_]*$",
        },
        "name": {"type": "string", "description": "Название ресурса"},
        "type": {
            "type": "string",
            "enum": ["web", "api", "json_ld", "table"],
            "default": "web",
            "description": "Тип ресурса",
        },
        "base_url": {
            "type": "string",
            "format": "uri",
            "description": "Базовый URL для поиска",
        },
        "search_url_template": {
            "type": "string",
            "description": "Шаблон URL для поиска (использует {isbn})",
        },
        "requires_browser": {
            "type": "boolean",
            "default": True,
            "description": "Требуется ли браузер для парсинга",
        },
        "selectors": {
            "type": "array",
            "items": {"$ref": "#/$defs/selector"},
            "default": [],
            "description": "Селекторы для извлечения данных",
        },
        "test_data": {
            "type": ["object", "null"],
            "properties": {
                "url": {
                    "type": "string",
                    "format": "uri",
                    "description": "URL тестовой страницы",
                },
                "html_fragment": {
                    "type": ["string", "null"],
                    "description": "HTML-фрагмент для тестирования",
                },
                "label_value_pairs": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "default": {},
                    "description": "Пары 'метка-значение' для тестирования",
                },
            },
            "required": ["url"],
            "additionalProperties": False,
            "description": "Тестовые данные для валидации и генерации селекторов",
        },
        "delay_range": {
            "type": "array",
            "items": {"type": "number", "minimum": 0.1},
            "minItems": 2,
            "maxItems": 2,
            "default": [1.0, 3.0],
            "description": "Диапазон задержек между запросами (секунды)",
        },
        "max_retries": {
            "type": "integer",
            "minimum": 0,
            "maximum": 10,
            "default": 3,
            "description": "Максимальное количество повторных попыток",
        },
        "timeout": {
            "type": "integer",
            "minimum": 5,
            "maximum": 120,
            "default": 30,
            "description": "Таймаут запроса (секунды)",
        },
        "custom_parser": {
            "type": ["string", "null"],
            "description": "Имя кастомного парсера (если требуется)",
        },
        "table_selector": {
            "type": ["string", "null"],
            "description": "Селектор таблицы (для ресурсов типа TABLE)",
        },
        "api_endpoint": {
            "type": ["string", "null"],
            "description": "API endpoint (для ресурсов типа API)",
        },
    },
    "$defs": {
        "selector": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Название поля (например, 'title', 'author')",
                },
                "pattern": {"type": "string", "description": "XPath или CSS-селектор"},
                "pattern_type": {
                    "type": "string",
                    "enum": ["xpath", "css", "regex"],
                    "default": "xpath",
                    "description": "Тип паттерна: 'xpath', 'css', 'regex'",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 1.0,
                    "description": "Уверенность в селекторе (0.0-1.0)",
                },
                "generated": {
                    "type": "boolean",
                    "default": False,
                    "description": "Был ли селектор сгенерирован автоматически",
                },
                "source": {
                    "type": ["string", "null"],
                    "description": "Источник селектора (debug_selectors, ручной)",
                },
            },
            "required": ["label", "pattern"],
            "additionalProperties": False,
        }
    },
    "required": ["id", "name", "base_url", "search_url_template"],
    "additionalProperties": False,
}

SCHEMA_RESOURCES_CONFIG_FILE = {
    "$schema": "http://json-schema.org/draft-2020-12/schema#",
    "title": "Resources Configuration File",
    "description": "Файл конфигурации ресурсов",
    "type": "object",
    "properties": {
        "resources": {
            "type": "array",
            "items": {"$ref": "#/$defs/resource"},
            "minItems": 1,
            "description": "Список конфигураций ресурсов",
        }
    },
    "$defs": {"resource": SCHEMA_RESOURCE_CONFIG},
    "required": ["resources"],
    "additionalProperties": False,
}

# Экспортируемые схемы
__all__ = [
    "SCHEMA_SCRAPER_CONFIG",
    "SCHEMA_RESOURCE_CONFIG",
    "SCHEMA_RESOURCES_CONFIG_FILE",
]
