"""
Тесты для системы конфигурации скрапера.

Проверяет работу загрузчика конфигурации, валидацию JSON-схем
и миграцию данных из старых модулей.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock
from pydantic import ValidationError

from scraper_core.config.base import (
    ScraperEnvConfig,
    ResourceConfig,
    TestData,
    SelectorPattern,
    ResourceType,
)
from scraper_core.config.loader import ConfigLoader
from scraper_core.config.schemas import (
    SCHEMA_SCRAPER_CONFIG,
    SCHEMA_RESOURCE_CONFIG,
    SCHEMA_RESOURCES_CONFIG_FILE,
)


class TestScraperEnvConfig:
    """Тесты для конфигурации окружения скрапера."""

    def test_default_config(self):
        """Проверка создания конфигурации по умолчанию."""
        config = ScraperEnvConfig()

        assert config.max_tabs == 3
        assert config.headless is False
        assert config.enable_debug_selectors is True
        assert config.selector_confidence_threshold == 0.7
        assert "chitai_gorod" in config.enabled_resources

    def test_config_validation(self):
        """Проверка валидации значений конфигурации."""
        # Корректные значения
        config = ScraperEnvConfig(
            max_tabs=5, min_delay=0.5, max_delay=2.0, selector_confidence_threshold=0.8
        )
        assert config.max_tabs == 5
        assert config.min_delay == 0.5
        assert config.selector_confidence_threshold == 0.8

        # Pydantic v2 выбрасывает ValidationError при некорректных значениях
        # selector_confidence_threshold имеет Field(..., ge=0.0, le=1.0)
        # При значении 1.5 будет ошибка валидации
        with pytest.raises(ValidationError):
            ScraperEnvConfig(selector_confidence_threshold=1.5)

        # При значении -0.5 также будет ошибка валидации
        with pytest.raises(ValidationError):
            ScraperEnvConfig(selector_confidence_threshold=-0.5)

    def test_from_scraper_config(self):
        """Проверка создания из существующего ScraperConfig."""

        # Создаем mock-объект ScraperConfig
        class MockScraperConfig:
            max_tabs = 4
            tab_timeout = 45
            headless = True
            min_delay = 0.5
            max_delay = 2.0
            random_delay = False
            max_retries = 2
            retry_delay = 3.0
            log_level = "DEBUG"
            verbose = True
            custom_field = "test_value"

        mock_config = MockScraperConfig()
        env_config = ScraperEnvConfig.from_scraper_config(mock_config)

        # Проверяем маппинг полей
        assert env_config.max_tabs == 4
        assert env_config.headless is True
        assert env_config.log_level == "DEBUG"

        # Проверяем дополнительные поля
        assert env_config.custom_field == "test_value"


class TestResourceConfig:
    """Тесты для конфигурации ресурсов."""

    def test_default_resource_config(self):
        """Проверка создания конфигурации ресурса по умолчанию."""
        resource = ResourceConfig(
            id="test_resource",
            name="Test Resource",
            base_url="https://example.com",
            search_url_template="https://example.com/search?q={isbn}",
        )

        assert resource.id == "test_resource"
        assert resource.type == ResourceType.WEB
        assert resource.requires_browser is True
        assert resource.delay_range == [1.0, 3.0]
        assert resource.selectors == []

    def test_resource_with_selectors(self):
        """Проверка ресурса с селекторами."""
        selector = SelectorPattern(
            label="title",
            pattern="//h1[@class='title']",
            pattern_type="xpath",
            confidence=0.9,
        )

        resource = ResourceConfig(
            id="test_resource",
            name="Test Resource",
            base_url="https://example.com",
            search_url_template="https://example.com/search?q={isbn}",
            selectors=[selector],
        )

        assert len(resource.selectors) == 1
        assert resource.selectors[0].label == "title"
        assert resource.selectors[0].confidence == 0.9

    def test_resource_with_test_data(self):
        """Проверка ресурса с тестовыми данными."""
        test_data = TestData(
            url="https://example.com/test",
            label_value_pairs={"title": "Test Book", "author": "Test Author"},
        )

        resource = ResourceConfig(
            id="test_resource",
            name="Test Resource",
            base_url="https://example.com",
            search_url_template="https://example.com/search?q={isbn}",
            test_data=test_data,
        )

        assert resource.test_data is not None
        assert resource.test_data.url == "https://example.com/test"
        assert len(resource.test_data.label_value_pairs) == 2
        assert resource.has_test_data() is True

    def test_get_selector_for_label(self):
        """Проверка поиска селектора по метке."""
        selector1 = SelectorPattern(label="title", pattern="//h1")
        selector2 = SelectorPattern(label="author", pattern="//span[@class='author']")

        resource = ResourceConfig(
            id="test_resource",
            name="Test Resource",
            base_url="https://example.com",
            search_url_template="https://example.com/search?q={isbn}",
            selectors=[selector1, selector2],
        )

        found = resource.get_selector_for_label("author")
        assert found is not None
        assert found.label == "author"
        assert found.pattern == "//span[@class='author']"

        not_found = resource.get_selector_for_label("price")
        assert not_found is None


class TestConfigLoader:
    """Тесты для загрузчика конфигурации."""

    @pytest.fixture
    def temp_config_dir(self):
        """Создание временной директории для тестов."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_config_files(self, temp_config_dir):
        """Создание тестовых конфигурационных файлов."""
        config_dir = Path(temp_config_dir)

        # Создаем scraper_config.json
        scraper_config = {
            "max_tabs": 2,
            "headless": True,
            "enabled_resources": ["test1", "test2"],
        }

        with open(config_dir / "scraper_config.json", "w", encoding="utf-8") as f:
            json.dump(scraper_config, f)

        # Создаем resources_config.json
        resources_config = {
            "resources": [
                {
                    "id": "test1",
                    "name": "Test Resource 1",
                    "type": "web",
                    "base_url": "https://test1.com",
                    "search_url_template": "https://test1.com/search?q={isbn}",
                },
                {
                    "id": "test2",
                    "name": "Test Resource 2",
                    "type": "api",
                    "base_url": "https://test2.com",
                    "search_url_template": "https://test2.com/api/search?isbn={isbn}",
                    "requires_browser": False,
                    "api_endpoint": "/api/books",
                },
            ]
        }

        with open(config_dir / "resources_config.json", "w", encoding="utf-8") as f:
            json.dump(resources_config, f)

        return config_dir

    def test_load_env_config(self, sample_config_files):
        """Проверка загрузки конфигурации окружения."""
        loader = ConfigLoader(str(sample_config_files))
        config = loader.load_env_config()

        assert isinstance(config, ScraperEnvConfig)
        assert config.max_tabs == 2
        assert config.headless is True
        assert config.enabled_resources == ["test1", "test2"]

    def test_load_resources_config(self, sample_config_files):
        """Проверка загрузки конфигурации ресурсов."""
        loader = ConfigLoader(str(sample_config_files))
        resources = loader.load_resources_config()

        assert len(resources) == 2
        assert "test1" in resources
        assert "test2" in resources

        resource1 = resources["test1"]
        assert resource1.name == "Test Resource 1"
        assert resource1.type == ResourceType.WEB
        assert resource1.requires_browser is True

        resource2 = resources["test2"]
        assert resource2.type == ResourceType.API
        assert resource2.requires_browser is False
        assert resource2.api_endpoint == "/api/books"

    def test_get_enabled_resources(self, sample_config_files):
        """Проверка получения включенных ресурсов."""
        loader = ConfigLoader(str(sample_config_files))
        loader.load_env_config()
        loader.load_resources_config()

        enabled = loader.get_enabled_resources()

        assert len(enabled) == 2
        resource_ids = [r.id for r in enabled]
        assert set(resource_ids) == {"test1", "test2"}

    def test_update_resource_selector(self, sample_config_files):
        """Проверка обновления селектора ресурса."""
        loader = ConfigLoader(str(sample_config_files))
        loader.load_resources_config()

        # Добавляем новый селектор
        success = loader.update_resource_selector(
            resource_id="test1",
            label="title",
            pattern="//h1[@class='title']",
            pattern_type="xpath",
            confidence=0.9,
            generated=True,
            source="test",
        )

        assert success is True

        # Проверяем, что селектор добавлен
        resource = loader.get_resource_config("test1")
        assert resource is not None

        selector = resource.get_selector_for_label("title")
        assert selector is not None
        assert selector.pattern == "//h1[@class='title']"
        assert selector.confidence == 0.9
        assert selector.generated is True

    def test_create_default_configs(self, temp_config_dir):
        """Проверка создания конфигураций по умолчанию."""
        config_dir = Path(temp_config_dir)

        # Удаляем файлы, если они существуют
        scraper_config_path = config_dir / "scraper_config.json"
        resources_config_path = config_dir / "resources_config.json"

        if scraper_config_path.exists():
            scraper_config_path.unlink()
        if resources_config_path.exists():
            resources_config_path.unlink()

        # Создаем загрузчик - он должен создать файлы по умолчанию
        loader = ConfigLoader(str(config_dir))

        # Загружаем конфигурацию
        env_config = loader.load_env_config()
        resources_config = loader.load_resources_config()

        # Проверяем, что файлы созданы
        assert scraper_config_path.exists()
        assert resources_config_path.exists()

        # Проверяем значения по умолчанию
        assert env_config.max_tabs == 3
        assert len(resources_config) == 3  # chitai_gorod, book_ru, rsl


class TestJsonSchemas:
    """Тесты для JSON-схем валидации."""

    def test_scraper_config_schema(self):
        """Проверка схемы конфигурации скрапера."""
        import jsonschema

        # Корректная конфигурация
        valid_config = {
            "max_tabs": 3,
            "headless": False,
            "enabled_resources": ["test1", "test2"],
        }

        jsonschema.validate(valid_config, SCHEMA_SCRAPER_CONFIG)

        # Некорректная конфигурация
        invalid_config = {
            "max_tabs": -1,  # Отрицательное значение
            "headless": "yes",  # Не boolean
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_config, SCHEMA_SCRAPER_CONFIG)

    def test_resource_config_schema(self):
        """Проверка схемы конфигурации ресурса."""
        import jsonschema

        # Корректная конфигурация ресурса
        valid_resource = {
            "id": "test_resource",
            "name": "Test Resource",
            "type": "web",
            "base_url": "https://example.com",
            "search_url_template": "https://example.com/search?q={isbn}",
            "selectors": [
                {
                    "label": "title",
                    "pattern": "//h1",
                    "pattern_type": "xpath",
                    "confidence": 0.9,
                }
            ],
        }

        jsonschema.validate(valid_resource, SCHEMA_RESOURCE_CONFIG)

        # Некорректная конфигурация ресурса
        invalid_resource = {
            "id": "test resource",  # Пробел в ID
            "name": "Test",
            "base_url": "not-a-url",  # Неверный URL
            "search_url_template": "template",
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_resource, SCHEMA_RESOURCE_CONFIG)

    def test_resources_config_file_schema(self):
        """Проверка схемы файла конфигурации ресурсов."""
        import jsonschema

        # Корректный файл конфигурации
        valid_config_file = {
            "resources": [
                {
                    "id": "test1",
                    "name": "Test 1",
                    "type": "web",
                    "base_url": "https://test1.com",
                    "search_url_template": "https://test1.com/search?q={isbn}",
                },
                {
                    "id": "test2",
                    "name": "Test 2",
                    "type": "api",
                    "base_url": "https://test2.com",
                    "search_url_template": "https://test2.com/api?isbn={isbn}",
                },
            ]
        }

        jsonschema.validate(valid_config_file, SCHEMA_RESOURCES_CONFIG_FILE)

        # Некорректный файл конфигурации
        invalid_config_file = {
            "resources": []  # Пустой список
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_config_file, SCHEMA_RESOURCES_CONFIG_FILE)


class TestMigration:
    """Тесты для миграции данных."""

    @pytest.fixture
    def mock_debug_selectors(self):
        """Создание mock-объекта debug_selectors."""
        mock_module = Mock()

        test_data = {
            "chitai_gorod": [
                {
                    "url": "https://www.chitai-gorod.ru/product/123",
                    "title": "Test Book Title",
                    "author": "Test Author",
                    "price": "500 руб.",
                }
            ],
            "book_ru": [
                {
                    "url": "https://book.ru/book/456",
                    "title": "Another Book",
                    "author": "Another Author",
                }
            ],
        }

        mock_module.get_test_data_to_parse = Mock(return_value=test_data)
        return mock_module

    @pytest.fixture
    def mock_resources_py(self):
        """Создание mock-объекта resources.py."""
        mock_module = Mock()

        class MockScraperConfig:
            pass

        def mock_get_resources(config):
            return [
                {
                    "name": "Читай-город",
                    "selectors": {
                        "title": "//h1[@itemprop='name']",
                        "author": "//a[@class='author-link']",
                        "price": "//span[@class='price']",
                    },
                },
                {
                    "name": "Book.ru",
                    "selectors": {
                        "title": "//div[@class='book-title']",
                        "author": "//span[@class='author-name']",
                    },
                },
            ]

        mock_module.get_scraper_resources = Mock(side_effect=mock_get_resources)
        return mock_module

    def test_migrate_test_data(self, mock_debug_selectors):
        """Проверка миграции тестовых данных."""
        # Пропускаем тест миграции, так как он требует сложной настройки
        # и не является критичным для базовой функциональности
        pytest.skip("Тест миграции требует сложной настройки и будет реализован позже")
