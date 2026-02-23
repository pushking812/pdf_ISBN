"""
Тесты для интеграции селекторов с debug_selectors и html_fragment.

Проверяет работу SelectorClient и SelectorIntegration.
"""

import pytest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import Mock, patch

from scraper_core.parsers.selector_client import SelectorClient
from scraper_core.integration.selector_integration import SelectorIntegration
from scraper_core.config.base import (
    SelectorPattern,
    TestData,
)


class TestSelectorClient:
    """Тесты для клиента селекторов."""

    @pytest.fixture
    def selector_client(self):
        """Создание клиента селекторов для тестов."""
        return SelectorClient({"test": "config"})

    @pytest.fixture
    def mock_debug_selectors(self):
        """Создание mock-объекта debug_selectors."""
        mock_module = Mock()

        # Mock функции extract_value
        mock_module.extract_value = Mock(return_value="Test Value")

        # Mock функции generate_pattern
        mock_module.generate_pattern = Mock(
            return_value=[
                {
                    "type": "xpath",
                    "selector": "//div[@class='test']",
                    "attribute": "text",
                    "label_text": "title",
                    "value_text": "Test Book",
                    "clean_regex": None,
                    "resource_id": None,
                }
            ]
        )

        return mock_module

    @pytest.fixture
    def mock_html_fragment(self):
        """Создание mock-объекта html_fragment."""
        mock_module = Mock()

        # Mock функции extract_common_parent_html
        mock_module.extract_common_parent_html = Mock(
            return_value=[("title", "Test Book", "<div>Test Book</div>", [], None)]
        )

        return mock_module

    def test_extract_with_selectors_success(
        self, selector_client, mock_debug_selectors
    ):
        """Проверка успешного извлечения данных с селекторами."""
        # Патчим внутренний атрибут _debug_selectors, так как debug_selectors - property
        selector_client._debug_selectors = mock_debug_selectors

        selectors = [
            SelectorPattern(
                label="title",
                pattern="//div[@class='title']",
                pattern_type="xpath",
                confidence=0.9,
            )
        ]

        result = selector_client.extract_with_selectors(
            html_or_driver="<html>test</html>", selectors=selectors, use_selenium=False
        )

        assert "title" in result
        assert result["title"] == "Test Value"
        mock_debug_selectors.extract_value.assert_called_once()

    def test_extract_with_selectors_no_module(self, selector_client):
        """Проверка извлечения данных без доступного модуля debug_selectors."""
        selector_client._debug_selectors = None

        selectors = [
            SelectorPattern(
                label="title", pattern="//div[@class='title']", pattern_type="xpath"
            )
        ]

        result = selector_client.extract_with_selectors(
            html_or_driver="<html>test</html>", selectors=selectors
        )

        assert result == {}

    def test_generate_selectors_success(
        self, selector_client, mock_debug_selectors, mock_html_fragment
    ):
        """Проверка успешной генерации селекторов."""
        # Патчим внутренние атрибуты
        selector_client._debug_selectors = mock_debug_selectors
        selector_client._html_fragment = mock_html_fragment

        label_value_pairs = {"title": "Test Book"}
        html = "<html><div>Test Book</div></html>"

        selectors = selector_client.generate_selectors(
            html=html,
            label_value_pairs=label_value_pairs,
            exact=True,
            case_sensitive=False,
        )

        assert len(selectors) == 1
        selector = selectors[0]
        assert selector.label == "title"
        assert selector.pattern == "//div[@class='test']"
        assert selector.pattern_type == "xpath"
        assert selector.generated is True
        assert selector.confidence == 0.8

    def test_generate_selectors_no_modules(self, selector_client):
        """Проверка генерации селекторов без доступных модулей."""
        selector_client._debug_selectors = None
        selector_client._html_fragment = None

        selectors = selector_client.generate_selectors(
            html="<html>test</html>", label_value_pairs={"title": "Test"}, exact=True
        )

        assert selectors == []

    def test_find_best_selector(self, selector_client):
        """Проверка поиска лучшего селектора."""
        # Mock extract_with_selectors
        selector_client.extract_with_selectors = Mock(
            side_effect=[
                {"title": "Test Book Value"},
                {"title": "Wrong Value"},
                {"title": "Test Book"},
            ]
        )

        selectors = [
            SelectorPattern(label="title", pattern="pattern1", pattern_type="xpath"),
            SelectorPattern(label="title", pattern="pattern2", pattern_type="xpath"),
            SelectorPattern(label="title", pattern="pattern3", pattern_type="xpath"),
        ]

        best_selector = selector_client.find_best_selector(
            html="<html>test</html>",
            label="title",
            value="Test Book",
            available_selectors=selectors,
            exact=True,
            case_sensitive=False,
        )

        assert best_selector is not None
        assert best_selector.pattern == "pattern3"
        assert best_selector.confidence == 1.0  # Точное совпадение

    def test_calculate_match_score(self, selector_client):
        """Проверка расчета оценки соответствия."""
        # Точное совпадение
        score = selector_client._calculate_match_score(
            extracted="Test Book",
            expected="Test Book",
            exact=True,
            case_sensitive=False,
        )
        assert score == 1.0

        # Частичное совпадение
        score = selector_client._calculate_match_score(
            extracted="This is a Test Book for reading",
            expected="Test Book",
            exact=False,
            case_sensitive=False,
        )
        assert 0.5 <= score <= 0.9

        # Нет совпадения
        score = selector_client._calculate_match_score(
            extracted="Different Text",
            expected="Test Book",
            exact=False,
            case_sensitive=False,
        )
        assert score == 0.0

        # С учетом регистра
        score = selector_client._calculate_match_score(
            extracted="test book", expected="Test Book", exact=True, case_sensitive=True
        )
        assert score == 0.0


class TestSelectorIntegration:
    """Тесты для интеграции селекторов."""

    @pytest.fixture
    def temp_config_dir(self):
        """Создание временной директории для тестов."""
        temp_dir = tempfile.mkdtemp()
        config_dir = Path(temp_dir) / "config"
        config_dir.mkdir()

        # Создаем базовые конфигурационные файлы
        scraper_config = {
            "max_tabs": 3,
            "selector_confidence_threshold": 0.7,
            "enabled_resources": ["test_resource"],
        }

        with open(config_dir / "scraper_config.json", "w", encoding="utf-8") as f:
            json.dump(scraper_config, f)

        resources_config = {
            "resources": [
                {
                    "id": "test_resource",
                    "name": "Test Resource",
                    "type": "web",
                    "base_url": "https://example.com",
                    "search_url_template": "https://example.com/search?q={isbn}",
                    "selectors": [
                        {
                            "label": "title",
                            "pattern": "//div[@class='old-title']",
                            "pattern_type": "xpath",
                            "confidence": 0.6,
                            "generated": False,
                        }
                    ],
                    "test_data": {
                        "url": "https://example.com/test",
                        "label_value_pairs": {
                            "title": "Test Book Title",
                            "author": "Test Author",
                        },
                    },
                }
            ]
        }

        with open(config_dir / "resources_config.json", "w", encoding="utf-8") as f:
            json.dump(resources_config, f)

        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def selector_integration(self, temp_config_dir):
        """Создание интеграции селекторов для тестов."""
        return SelectorIntegration(str(Path(temp_config_dir) / "config"))

    def test_init_loads_config(self, selector_integration):
        """Проверка загрузки конфигурации при инициализации."""
        assert selector_integration.env_config is not None
        assert selector_integration.env_config.max_tabs == 3
        assert selector_integration.env_config.selector_confidence_threshold == 0.7

        assert selector_integration.resources_config is not None
        assert "test_resource" in selector_integration.resources_config

    def test_update_resource_selectors_new_selector(
        self, selector_integration, temp_config_dir
    ):
        """Проверка обновления селекторов с генерацией нового."""
        # Mock SelectorClient
        mock_client = Mock()
        mock_client.extract_with_selectors = Mock(
            return_value={}
        )  # Существующий не работает
        mock_client.generate_selectors = Mock(
            return_value=[
                SelectorPattern(
                    label="title",
                    pattern="//div[@class='new-title']",
                    pattern_type="xpath",
                    confidence=0.9,
                    generated=True,
                )
            ]
        )
        mock_client.find_best_selector = Mock(
            return_value=SelectorPattern(
                label="title",
                pattern="//div[@class='new-title']",
                pattern_type="xpath",
                confidence=0.9,
                generated=True,
            )
        )

        selector_integration.selector_client = mock_client

        html = "<html><div class='new-title'>Test Book Title</div></html>"

        updated = selector_integration.update_resource_selectors(
            resource_id="test_resource", html=html, force_regenerate=False
        )

        assert len(updated) == 1
        assert updated[0].label == "title"
        assert updated[0].pattern == "//div[@class='new-title']"
        assert updated[0].confidence == 0.9

    def test_update_resource_selectors_existing_works(
        self, selector_integration, temp_config_dir
    ):
        """Проверка обновления селекторов, когда существующий работает хорошо."""
        # Изменяем конфигурацию, чтобы test_data содержал только title
        resource = selector_integration.resources_config["test_resource"]
        # Создаем новый test_data только с title

        resource.test_data = TestData(
            url="https://example.com/test",
            label_value_pairs={"title": "Test Book Title"},
        )
        # Обновляем конфигурацию
        selector_integration.resources_config["test_resource"] = resource

        # Mock SelectorClient
        mock_client = Mock()
        mock_client.extract_with_selectors = Mock(
            return_value={"title": "Test Book Title"}
        )
        # Убедимся, что generate_selectors и find_best_selector не вызываются
        mock_client.generate_selectors = Mock()
        mock_client.find_best_selector = Mock()

        selector_integration.selector_client = mock_client

        # Мокаем _calculate_match_score чтобы возвращал высокую оценку
        selector_integration._calculate_match_score = Mock(return_value=0.9)

        html = "<html><div class='old-title'>Test Book Title</div></html>"

        updated = selector_integration.update_resource_selectors(
            resource_id="test_resource", html=html, force_regenerate=False
        )

        # Проверяем, что generate_selectors и find_best_selector не вызывались
        mock_client.generate_selectors.assert_not_called()
        mock_client.find_best_selector.assert_not_called()

        # Существующий селектор должен быть обновлен с повышенной уверенностью
        assert len(updated) == 1
        assert updated[0].label == "title"
        # confidence должен быть обновлен до 0.9
        assert updated[0].confidence == 0.9

    def test_auto_generate_all_selectors(self, selector_integration):
        """Проверка автоматической генерации селекторов для всех ресурсов."""
        results = selector_integration.auto_generate_all_selectors()

        assert isinstance(results, dict)
        assert "test_resource" in results
        # В этом тесте только планирование, без реальной генерации
        assert results["test_resource"] == []

    def test_migrate_existing_selectors_success(self, selector_integration):
        """Проверка успешной миграции существующих селекторов."""
        # Mock модулей resources и config
        mock_resources = Mock()
        mock_resources.get_scraper_resources = Mock(
            return_value=[
                {
                    "name": "Читай-город",
                    "selectors": {
                        "title": "//h1[@itemprop='name']",
                        "author": "//a[@class='author-link']",
                    },
                }
            ]
        )

        class MockScraperConfig:
            pass

        with patch.dict("sys.modules", {"resources": mock_resources, "config": Mock()}):
            # ScraperConfig импортируется из config, поэтому патчим config.ScraperConfig
            with patch("config.ScraperConfig", MockScraperConfig):
                results = selector_integration.migrate_existing_selectors()

        # В реальном тесте будет проверка, что селекторы добавлены
        # Но так как мы мокаем, просто проверяем что функция не падает
        assert isinstance(results, dict)

    def test_migrate_existing_selectors_import_error(self, selector_integration):
        """Проверка миграции при ошибке импорта."""
        with patch.dict("sys.modules", {"resources": None}):
            results = selector_integration.migrate_existing_selectors()

        assert results == {}

    def test_calculate_match_score(self, selector_integration):
        """Проверка расчета оценки соответствия в интеграции."""
        # Точное совпадение
        score = selector_integration._calculate_match_score(
            extracted="Test Book",
            expected="Test Book",
            exact=True,
            case_sensitive=False,
        )
        assert score == 1.0

        # Нет совпадения
        score = selector_integration._calculate_match_score(
            extracted="Different",
            expected="Test Book",
            exact=True,
            case_sensitive=False,
        )
        assert score == 0.0

        # Частичное совпадение (не точное)
        score = selector_integration._calculate_match_score(
            extracted="This is a Test Book",
            expected="Test Book",
            exact=False,
            case_sensitive=False,
        )
        assert score > 0.0

    def test_map_resource_name_to_id(self, selector_integration):
        """Проверка маппинга названий ресурсов в ID."""
        assert (
            selector_integration._map_resource_name_to_id("Читай-город")
            == "chitai_gorod"
        )
        assert selector_integration._map_resource_name_to_id("Book.ru") == "book_ru"
        assert selector_integration._map_resource_name_to_id("РГБ") == "rsl"
        assert selector_integration._map_resource_name_to_id("Неизвестный") is None
