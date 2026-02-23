"""
Базовые классы конфигурации для скрапера.

Содержит базовые Pydantic-модели для валидации конфигурационных данных.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class ResourceType(str, Enum):
    """Типы ресурсов для парсинга."""

    WEB = "web"  # Веб-страницы с использованием браузера
    API = "api"  # API-клиенты
    JSON_LD = "json_ld"  # JSON-LD структурированные данные
    TABLE = "table"  # Табличные данные


class SelectorPattern(BaseModel):
    """Паттерн селектора для извлечения данных."""

    label: str = Field(..., description="Название поля (например, 'title', 'author')")
    pattern: str = Field(..., description="XPath или CSS-селектор")
    pattern_type: str = Field(
        "xpath", description="Тип паттерна: 'xpath', 'css', 'regex'"
    )
    confidence: float = Field(1.0, description="Уверенность в селекторе (0.0-1.0)")
    generated: bool = Field(
        False, description="Был ли селектор сгенерирован автоматически"
    )
    source: Optional[str] = Field(
        None, description="Источник селектора (debug_selectors, ручной)"
    )

    @validator("confidence")
    def validate_confidence(cls, v):
        if v < 0.0 or v > 1.0:
            raise ValueError("confidence должен быть в диапазоне 0.0-1.0")
        return v


class TestData(BaseModel):
    """Тестовые данные для ресурса."""

    url: str = Field(..., description="URL тестовой страницы")
    html_fragment: Optional[str] = Field(
        None, description="HTML-фрагмент для тестирования"
    )
    label_value_pairs: Dict[str, str] = Field(
        default_factory=dict, description="Пары 'метка-значение' для тестирования"
    )


class ResourceConfig(BaseModel):
    """Конфигурация ресурса для парсинга."""

    id: str = Field(..., description="Уникальный идентификатор ресурса")
    name: str = Field(..., description="Название ресурса")
    type: ResourceType = Field(ResourceType.WEB, description="Тип ресурса")

    # Основные параметры
    base_url: str = Field(..., description="Базовый URL для поиска")
    search_url_template: str = Field(
        ..., description="Шаблон URL для поиска (использует {isbn})"
    )
    requires_browser: bool = Field(
        True, description="Требуется ли браузер для парсинга"
    )

    # Селекторы
    selectors: List[SelectorPattern] = Field(
        default_factory=list, description="Селекторы для извлечения данных"
    )

    # Тестовые данные
    test_data: Optional[TestData] = Field(
        None, description="Тестовые данные для валидации и генерации селекторов"
    )

    # Дополнительные параметры
    delay_range: List[float] = Field(
        [1.0, 3.0], description="Диапазон задержек между запросами (секунды)"
    )
    max_retries: int = Field(3, description="Максимальное количество повторных попыток")
    timeout: int = Field(30, description="Таймаут запроса (секунды)")

    # Параметры для специфичных ресурсов
    custom_parser: Optional[str] = Field(
        None, description="Имя кастомного парсера (если требуется)"
    )
    table_selector: Optional[str] = Field(
        None, description="Селектор таблицы (для ресурсов типа TABLE)"
    )
    api_endpoint: Optional[str] = Field(
        None, description="API endpoint (для ресурсов типа API)"
    )

    class Config:
        use_enum_values = True

    @validator("delay_range")
    def validate_delay_range(cls, v):
        if len(v) != 2:
            raise ValueError("delay_range должен содержать 2 значения [min, max]")
        if v[0] < 0 or v[1] < 0:
            raise ValueError("Задержки не могут быть отрицательными")
        if v[0] > v[1]:
            raise ValueError("Минимальная задержка должна быть меньше максимальной")
        return v

    def get_selector_for_label(self, label: str) -> Optional[SelectorPattern]:
        """Получить селектор для указанной метки."""
        for selector in self.selectors:
            if selector.label == label:
                return selector
        return None

    def has_test_data(self) -> bool:
        """Проверить, есть ли тестовые данные."""
        return self.test_data is not None and bool(self.test_data.label_value_pairs)


class ScraperEnvConfig(BaseModel):
    """Конфигурация окружения скрапера (наследуется от ScraperConfig)."""

    # Основные параметры
    max_tabs: int = Field(3, description="Максимальное количество вкладок браузера")
    tab_timeout: int = Field(60, description="Таймаут для вкладки (секунды)")
    headless: bool = Field(False, description="Запуск браузера в headless-режиме")
    user_agent: Optional[str] = Field(None, description="Пользовательский User-Agent")

    # Параметры задержек
    min_delay: float = Field(1.0, description="Минимальная задержка между запросами")
    max_delay: float = Field(3.0, description="Максимальная задержка между запросами")
    random_delay: bool = Field(True, description="Использовать случайные задержки")

    # Параметры повторных попыток
    max_retries: int = Field(3, description="Максимальное количество повторных попыток")
    retry_delay: float = Field(5.0, description="Задержка между повторными попытками")

    # Параметры логирования
    log_level: str = Field("INFO", description="Уровень логирования")
    verbose: bool = Field(False, description="Подробный вывод")

    # Пути к файлам
    config_dir: str = Field(
        "config", description="Директория с конфигурационными файлами"
    )
    cache_dir: str = Field("cache", description="Директория для кэша")
    output_dir: str = Field("output", description="Директория для вывода")

    # Параметры интеграции
    enable_debug_selectors: bool = Field(
        True, description="Включить интеграцию с debug_selectors"
    )
    auto_generate_selectors: bool = Field(
        True, description="Автоматически генерировать отсутствующие селекторы"
    )
    selector_confidence_threshold: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Порог уверенности для использования селектора (0.0-1.0)",
    )

    # Список ресурсов
    enabled_resources: List[str] = Field(
        default_factory=lambda: ["chitai_gorod", "book_ru", "rsl"],
        description="Список включенных ресурсов",
    )

    class Config:
        extra = "allow"  # Разрешить дополнительные поля для совместимости

    @classmethod
    def from_scraper_config(cls, scraper_config: Any) -> "ScraperEnvConfig":
        """
        Создать ScraperEnvConfig из существующего объекта ScraperConfig.

        Args:
            scraper_config: Экземпляр ScraperConfig из config.py

        Returns:
            ScraperEnvConfig с параметрами из scraper_config
        """
        # Получаем атрибуты из scraper_config
        config_dict = {}

        # Маппинг полей ScraperConfig -> ScraperEnvConfig
        field_mapping = {
            "max_tabs": "max_tabs",
            "tab_timeout": "tab_timeout",
            "headless": "headless",
            "user_agent": "user_agent",
            "min_delay": "min_delay",
            "max_delay": "max_delay",
            "random_delay": "random_delay",
            "max_retries": "max_retries",
            "retry_delay": "retry_delay",
            "log_level": "log_level",
            "verbose": "verbose",
        }

        for scraper_field, env_field in field_mapping.items():
            if hasattr(scraper_config, scraper_field):
                config_dict[env_field] = getattr(scraper_config, scraper_field)

        # Добавляем дополнительные поля из scraper_config как extra
        for attr_name in dir(scraper_config):
            if not attr_name.startswith("_") and attr_name not in field_mapping:
                attr_value = getattr(scraper_config, attr_name)
                if not callable(attr_value):
                    config_dict[attr_name] = attr_value

        return cls(**config_dict)
