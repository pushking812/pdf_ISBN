"""
Scraper Core - новая модульная архитектура для скрапинга книг по ISBN.

Основные компоненты:
- config: Конфигурация системы (ScraperEnvConfig, ResourceConfig)
- isbn: Обработка и валидация ISBN
- handlers: Обработчики ресурсов (веб-сайты, API, JSON-LD, таблицы)
- orchestrator: Оркестрационный слой для управления процессом скрапинга
- parsers: Парсеры для извлечения данных (SelectorClient, JsonLdParser, TableParser)
- utils: Утилиты (метрики, анти-бот защита, кэширование)
- drivers: Управление ChromeDriver
- integration: Интеграция с существующим кодом

Версия: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Scraper Core Team"

# Экспорт основных классов
from .config.base import (
    ScraperEnvConfig,
    ResourceConfig,
    TestData,
    SelectorPattern,
    ResourceType,
)
from .config.loader import ConfigLoader

from .isbn.utils import validate_isbn10, validate_isbn13, normalize_isbn
from .isbn.processor import ISBNProcessor

from .handlers.base import ResourceHandler
from .handlers.factory import ResourceHandlerFactory

from .orchestrator.core import ScraperOrchestrator

from .parsers.selector_client import SelectorClient

__all__ = [
    # Конфигурация
    "ScraperEnvConfig",
    "ResourceConfig",
    "TestData",
    "SelectorPattern",
    "ResourceType",
    "ConfigLoader",
    # ISBN
    "validate_isbn10",
    "validate_isbn13",
    "normalize_isbn",
    "ISBNProcessor",
    # Обработчики
    "ResourceHandler",
    "ResourceHandlerFactory",
    # Оркестратор
    "ScraperOrchestrator",
    # Парсеры
    "SelectorClient",
]
