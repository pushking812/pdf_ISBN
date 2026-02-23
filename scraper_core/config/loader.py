"""
Загрузчик конфигурации для скрапера.

Обеспечивает загрузку конфигурации из JSON-файлов и интеграцию
с существующим ScraperConfig из config.py.
"""

import json
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from .base import ScraperEnvConfig, ResourceConfig, TestData, SelectorPattern

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Загрузчик и валидатор конфигурации скрапера."""

    def __init__(self, config_dir: str = "config"):
        """
        Инициализация загрузчика конфигурации.

        Args:
            config_dir: Директория с конфигурационными файлами
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)

        # Кэшированные конфигурации
        self._env_config: Optional[ScraperEnvConfig] = None
        self._resources_config: Dict[str, ResourceConfig] = {}

    def load_env_config(self, config_path: Optional[str] = None) -> ScraperEnvConfig:
        """
        Загрузить конфигурацию окружения скрапера.

        Args:
            config_path: Путь к JSON-файлу конфигурации.
                        Если None, используется config/scraper_config.json

        Returns:
            ScraperEnvConfig: Загруженная конфигурация
        """
        if config_path is None:
            config_path = self.config_dir / "scraper_config.json"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            logger.warning(f"Файл конфигурации не найден: {config_path}")
            logger.info("Создаю конфигурацию по умолчанию")
            self._env_config = ScraperEnvConfig()
            self._save_default_env_config(config_path)
            return self._env_config

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            self._env_config = ScraperEnvConfig(**config_data)
            logger.info(f"Конфигурация окружения загружена из {config_path}")
            return self._env_config

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON в {config_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации из {config_path}: {e}")
            raise

    def load_resources_config(
        self, config_path: Optional[str] = None
    ) -> Dict[str, ResourceConfig]:
        """
        Загрузить конфигурацию ресурсов.

        Args:
            config_path: Путь к JSON-файлу конфигурации ресурсов.
                        Если None, используется config/resources_config.json

        Returns:
            Dict[str, ResourceConfig]: Словарь конфигураций ресурсов по ID
        """
        if config_path is None:
            config_path = self.config_dir / "resources_config.json"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            logger.warning(f"Файл конфигурации ресурсов не найден: {config_path}")
            logger.info("Создаю конфигурацию по умолчанию")
            self._create_default_resources_config(config_path)

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            self._resources_config = {}
            for resource_data in config_data.get("resources", []):
                resource = ResourceConfig(**resource_data)
                self._resources_config[resource.id] = resource

            logger.info(f"Конфигурация ресурсов загружена из {config_path}")
            logger.info(f"Загружено ресурсов: {len(self._resources_config)}")
            return self._resources_config

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON в {config_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации ресурсов из {config_path}: {e}")
            raise

    def get_resource_config(self, resource_id: str) -> Optional[ResourceConfig]:
        """
        Получить конфигурацию ресурса по ID.

        Args:
            resource_id: Идентификатор ресурса

        Returns:
            ResourceConfig или None, если ресурс не найден
        """
        if not self._resources_config:
            self.load_resources_config()

        return self._resources_config.get(resource_id)

    def get_enabled_resources(self) -> List[ResourceConfig]:
        """
        Получить список включенных ресурсов.

        Returns:
            List[ResourceConfig]: Список конфигураций включенных ресурсов
        """
        if self._env_config is None:
            self.load_env_config()

        enabled_resources = []
        for resource_id in self._env_config.enabled_resources:
            resource = self.get_resource_config(resource_id)
            if resource:
                enabled_resources.append(resource)
            else:
                logger.warning(
                    f"Ресурс {resource_id} включен в конфигурации, но не найден"
                )

        return enabled_resources

    def update_resource_selector(
        self,
        resource_id: str,
        label: str,
        pattern: str,
        pattern_type: str = "xpath",
        confidence: float = 1.0,
        generated: bool = False,
        source: Optional[str] = None,
    ) -> bool:
        """
        Обновить или добавить селектор для ресурса.

        Args:
            resource_id: Идентификатор ресурса
            label: Метка поля
            pattern: Паттерн селектора
            pattern_type: Тип паттерна
            confidence: Уверенность в селекторе
            generated: Был ли селектор сгенерирован
            source: Источник селектора

        Returns:
            bool: True если успешно обновлено
        """
        resource = self.get_resource_config(resource_id)
        if not resource:
            logger.error(f"Ресурс {resource_id} не найден")
            return False

        # Проверяем, существует ли уже селектор для этой метки
        existing_selector = None
        for i, selector in enumerate(resource.selectors):
            if selector.label == label:
                existing_selector = i
                break

        new_selector = SelectorPattern(
            label=label,
            pattern=pattern,
            pattern_type=pattern_type,
            confidence=confidence,
            generated=generated,
            source=source,
        )

        if existing_selector is not None:
            # Обновляем существующий селектор
            resource.selectors[existing_selector] = new_selector
            logger.debug(f"Обновлен селектор для {label} в ресурсе {resource_id}")
        else:
            # Добавляем новый селектор
            resource.selectors.append(new_selector)
            logger.debug(f"Добавлен новый селектор для {label} в ресурсе {resource_id}")

        # Сохраняем изменения
        return self._save_resources_config()

    def migrate_from_debug_selectors(
        self, debug_selectors_module: Any
    ) -> Dict[str, List[SelectorPattern]]:
        """
        Мигрировать тестовые данные и селекторы из debug_selectors.py.

        Args:
            debug_selectors_module: Модуль debug_selectors.py

        Returns:
            Dict[str, List[SelectorPattern]]: Словарь сгенерированных селекторов по resource_id
        """
        try:
            # Получаем тестовые данные из debug_selectors
            test_data_func = getattr(
                debug_selectors_module, "get_test_data_to_parse", None
            )
            if not test_data_func:
                logger.error(
                    "Функция get_test_data_to_parse не найдена в debug_selectors"
                )
                return {}

            test_data = test_data_func()
            logger.info(f"Получены тестовые данные для {len(test_data)} ресурсов")

            generated_selectors = {}

            for resource_id, test_cases in test_data.items():
                if not test_cases:
                    continue

                # Берем первый тестовый случай для извлечения данных
                test_case = test_cases[0]
                url = test_case.get("url", "")
                label_value_pairs = {
                    k: v
                    for k, v in test_case.items()
                    if k not in ["url", "html_fragment"]
                }

                # Создаем или обновляем тестовые данные в конфигурации
                resource = self.get_resource_config(resource_id)
                if resource:
                    if not resource.test_data:
                        resource.test_data = TestData(
                            url=url, label_value_pairs=label_value_pairs
                        )
                    else:
                        # Обновляем существующие тестовые данные
                        resource.test_data.url = url
                        resource.test_data.label_value_pairs.update(label_value_pairs)

                    logger.info(f"Обновлены тестовые данные для ресурса {resource_id}")

                    # Генерируем селекторы (это будет сделано позже в Итерации 2)
                    # Пока просто отмечаем, что тестовые данные есть
                    generated_selectors[resource_id] = []

            # Сохраняем изменения
            self._save_resources_config()
            return generated_selectors

        except Exception as e:
            logger.error(f"Ошибка миграции из debug_selectors: {e}")
            return {}

    def _save_default_env_config(self, config_path: Path) -> None:
        """Сохранить конфигурацию окружения по умолчанию."""
        default_config = ScraperEnvConfig()
        config_data = default_config.dict()

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Создана конфигурация окружения по умолчанию: {config_path}")

    def _create_default_resources_config(self, config_path: Path) -> None:
        """Создать конфигурацию ресурсов по умолчанию."""
        default_resources = [
            {
                "id": "chitai_gorod",
                "name": "Читай-город",
                "type": "web",
                "base_url": "https://www.chitai-gorod.ru",
                "search_url_template": "https://www.chitai-gorod.ru/search?phrase={isbn}",
                "requires_browser": True,
                "selectors": [],
                "delay_range": [1.0, 3.0],
                "max_retries": 3,
                "timeout": 30,
            },
            {
                "id": "book_ru",
                "name": "Book.ru",
                "type": "web",
                "base_url": "https://book.ru",
                "search_url_template": "https://book.ru/search?q={isbn}",
                "requires_browser": True,
                "selectors": [],
                "delay_range": [1.0, 3.0],
                "max_retries": 3,
                "timeout": 30,
                "custom_parser": "book_ru_table_parser",
            },
            {
                "id": "rsl",
                "name": "РГБ (Российская государственная библиотека)",
                "type": "table",
                "base_url": "https://search.rsl.ru",
                "search_url_template": "https://search.rsl.ru/ru/search?q={isbn}",
                "requires_browser": False,
                "selectors": [],
                "delay_range": [2.0, 5.0],
                "max_retries": 2,
                "timeout": 45,
                "table_selector": "table.search-results",
            },
        ]

        config_data = {"resources": default_resources}

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Создана конфигурация ресурсов по умолчанию: {config_path}")

        # Загружаем созданную конфигурацию
        self.load_resources_config(config_path)

    def _save_resources_config(self, config_path: Optional[Path] = None) -> bool:
        """
        Сохранить конфигурацию ресурсов в файл.

        Args:
            config_path: Путь для сохранения

        Returns:
            bool: True если успешно сохранено
        """
        if config_path is None:
            config_path = self.config_dir / "resources_config.json"

        try:
            resources_data = []
            for resource in self._resources_config.values():
                resource_dict = resource.dict()
                resources_data.append(resource_dict)

            config_data = {"resources": resources_data}

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Конфигурация ресурсов сохранена в {config_path}")
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации ресурсов: {e}")
            return False


def create_config_from_existing(
    existing_config: Any, config_dir: str = "config"
) -> ScraperEnvConfig:
    """
    Создать ScraperEnvConfig из существующего объекта конфигурации.

    Args:
        existing_config: Существующий объект конфигурации (например, из config.py)
        config_dir: Директория для сохранения конфигурации

    Returns:
        ScraperEnvConfig: Новая конфигурация
    """
    loader = ConfigLoader(config_dir)

    # Создаем ScraperEnvConfig из существующей конфигурации
    env_config = ScraperEnvConfig.from_scraper_config(existing_config)

    # Сохраняем в файл
    config_path = Path(config_dir) / "scraper_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(env_config.dict(), f, indent=2, ensure_ascii=False)

    logger.info(f"Конфигурация создана из существующей и сохранена в {config_path}")
    return env_config
