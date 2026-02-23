"""
Тесты для SearchCoordinator.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from scraper_core.orchestrator.search import (
    SearchCoordinator,
    ResourceStats,
    ResourceStatus,
)
from scraper_core.config.loader import ConfigLoader


class TestResourceStats:
    """Тесты для класса ResourceStats."""

    def test_initialization(self):
        """Тест инициализации ResourceStats."""
        stats = ResourceStats(resource_id="test-resource")

        assert stats.resource_id == "test-resource"
        assert stats.total_attempts == 0
        assert stats.successful_attempts == 0
        assert stats.failed_attempts == 0
        assert stats.rate_limit_events == 0
        assert stats.total_response_time == 0.0
        assert stats.last_used is None
        assert stats.last_error is None
        assert stats.error_count == 0

    def test_success_rate_with_no_attempts(self):
        """Тест коэффициента успешности без попыток."""
        stats = ResourceStats(resource_id="test-resource")
        assert stats.success_rate == 1.0  # По умолчанию считаем ресурс надежным

    def test_success_rate_with_attempts(self):
        """Тест коэффициента успешности с попытками."""
        stats = ResourceStats(
            resource_id="test-resource", total_attempts=10, successful_attempts=7
        )
        assert stats.success_rate == 0.7

    def test_avg_response_time_with_no_success(self):
        """Тест среднего времени ответа без успешных попыток."""
        stats = ResourceStats(resource_id="test-resource")
        assert stats.avg_response_time == 0.0

    def test_avg_response_time_with_success(self):
        """Тест среднего времени ответа с успешными попытками."""
        stats = ResourceStats(
            resource_id="test-resource", successful_attempts=3, total_response_time=6.0
        )
        assert stats.avg_response_time == 2.0

    def test_availability_score_calculation(self):
        """Тест расчета оценки доступности."""
        stats = ResourceStats(
            resource_id="test-resource",
            total_attempts=20,
            successful_attempts=15,
            error_count=2,
            last_used=datetime.now() - timedelta(minutes=30),  # 30 минут назад
        )

        # Проверяем, что оценка в пределах 0-1
        score = stats.availability_score
        assert 0.0 <= score <= 1.0

        # Проверяем логику расчета
        success_score = 0.75 * 0.6  # 15/20 = 0.75, вес 0.6
        error_penalty = (2 / 20) * 0.2  # error_rate = 0.1, вес 0.2
        recency_bonus = 0.2  # использовался менее часа назад

        expected_score = success_score - error_penalty + recency_bonus
        assert abs(score - expected_score) < 0.01


class TestSearchCoordinator:
    """Тесты для класса SearchCoordinator."""

    @pytest.fixture
    def mock_config_loader(self):
        """Mock ConfigLoader."""
        with patch("scraper_core.orchestrator.search.ConfigLoader") as mock:
            loader = Mock()
            loader.load_resources_config.return_value = {
                "resource-1": Mock(
                    id="resource-1",
                    name="Ресурс 1",
                    type="web",
                    priority=1,
                    search_url_template="https://test1.com/search?isbn={isbn}",
                ),
                "resource-2": Mock(
                    id="resource-2",
                    name="Ресурс 2",
                    type="api",
                    priority=2,
                    api_endpoint="https://api.test2.com/books/{isbn}",
                ),
                "resource-3": Mock(
                    id="resource-3",
                    name="Ресурс 3",
                    type="web",
                    priority=3,
                    search_url_template="https://test3.com/search?isbn={isbn}",
                ),
            }
            mock.return_value = loader
            yield loader

    @pytest.fixture
    def coordinator(self, mock_config_loader):
        """Создание экземпляра SearchCoordinator."""
        enabled_resources = ["resource-1", "resource-2", "resource-3"]
        return SearchCoordinator(
            config_loader=mock_config_loader, enabled_resources=enabled_resources
        )

    def test_initialization(self, coordinator):
        """Тест инициализации SearchCoordinator."""
        assert coordinator is not None
        assert len(coordinator.resource_stats) == 3
        assert "resource-1" in coordinator.resource_stats
        assert "resource-2" in coordinator.resource_stats
        assert "resource-3" in coordinator.resource_stats

        # Проверяем начальные статусы
        for resource_id in coordinator.resource_stats:
            assert (
                coordinator.get_resource_status(resource_id) == ResourceStatus.AVAILABLE
            )

    def test_get_next_resource_with_no_tried(self, coordinator):
        """Тест выбора следующего ресурса без ранее использованных."""
        resource_id = coordinator.get_next_resource(
            task_isbn="9781234567890", tried_resources=set()
        )

        # Должен вернуть один из доступных ресурсов
        assert resource_id in ["resource-1", "resource-2", "resource-3"]

        # Приоритет должен быть у resource-1 (priority=1)
        # Но из-за случайности в выборе можем проверить только наличие
        assert resource_id is not None

    def test_get_next_resource_with_tried(self, coordinator):
        """Тест выбора следующего ресурса с исключенными ресурсами."""
        # Исключаем первые два ресурса
        tried_resources = {"resource-1", "resource-2"}

        resource_id = coordinator.get_next_resource(
            task_isbn="9781234567890", tried_resources=tried_resources
        )

        # Должен вернуть resource-3 (единственный доступный)
        assert resource_id == "resource-3"

    def test_get_next_resource_all_tried(self, coordinator):
        """Тест выбора следующего ресурса, когда все ресурсы уже использованы."""
        tried_resources = {"resource-1", "resource-2", "resource-3"}

        resource_id = coordinator.get_next_resource(
            task_isbn="9781234567890", tried_resources=tried_resources
        )

        # Должен вернуть None
        assert resource_id is None

    def test_update_resource_stats_success(self, coordinator):
        """Тест обновления статистики при успешном выполнении."""
        resource_id = "resource-1"

        # Получаем начальную статистику
        initial_stats = coordinator.resource_stats[resource_id]
        initial_attempts = initial_stats.total_attempts
        initial_successes = initial_stats.successful_attempts

        # Обновляем статистику для успешного выполнения
        coordinator.update_resource_stats(
            resource_id=resource_id,
            success=True,
            response_time=2.5,
            error_message=None,
            rate_limited=False,
        )

        # Проверяем обновленную статистику
        updated_stats = coordinator.resource_stats[resource_id]
        assert updated_stats.total_attempts == initial_attempts + 1
        assert updated_stats.successful_attempts == initial_successes + 1
        assert updated_stats.failed_attempts == 0
        assert updated_stats.total_response_time == 2.5
        assert updated_stats.last_used is not None
        assert updated_stats.last_error is None
        assert updated_stats.error_count == 0

    def test_update_resource_stats_failure(self, coordinator):
        """Тест обновления статистики при неудачном выполнении."""
        resource_id = "resource-2"

        # Обновляем статистику для неудачного выполнения
        coordinator.update_resource_stats(
            resource_id=resource_id,
            success=False,
            response_time=1.0,
            error_message="Connection timeout",
            rate_limited=False,
        )

        # Проверяем обновленную статистику
        updated_stats = coordinator.resource_stats[resource_id]
        assert updated_stats.total_attempts == 1
        assert updated_stats.successful_attempts == 0
        assert updated_stats.failed_attempts == 1
        assert updated_stats.total_response_time == 0.0  # Не добавляется для неудачных
        assert updated_stats.last_used is not None
        assert updated_stats.last_error == "Connection timeout"
        assert updated_stats.error_count == 1

    def test_update_resource_stats_rate_limited(self, coordinator):
        """Тест обновления статистики при rate limit."""
        resource_id = "resource-3"

        # Обновляем статистику для rate limit
        coordinator.update_resource_stats(
            resource_id=resource_id,
            success=False,
            response_time=0.5,
            error_message="Rate limit exceeded",
            rate_limited=True,
        )

        # Проверяем обновленную статистику
        updated_stats = coordinator.resource_stats[resource_id]
        assert updated_stats.total_attempts == 1
        assert updated_stats.successful_attempts == 0
        assert updated_stats.failed_attempts == 1
        assert updated_stats.rate_limit_events == 1
        assert updated_stats.last_error == "Rate limit exceeded"

        # Проверяем, что статус изменился на RATE_LIMITED
        assert (
            coordinator.get_resource_status(resource_id) == ResourceStatus.RATE_LIMITED
        )

    def test_get_resource_status(self, coordinator):
        """Тест получения статуса ресурса."""
        # По умолчанию все ресурсы AVAILABLE
        assert coordinator.get_resource_status("resource-1") == ResourceStatus.AVAILABLE
        assert coordinator.get_resource_status("resource-2") == ResourceStatus.AVAILABLE

        # Устанавливаем статус RATE_LIMITED
        coordinator.set_resource_status("resource-1", ResourceStatus.RATE_LIMITED)
        assert (
            coordinator.get_resource_status("resource-1") == ResourceStatus.RATE_LIMITED
        )

        # Устанавливаем статус ERROR
        coordinator.set_resource_status("resource-2", ResourceStatus.ERROR)
        assert coordinator.get_resource_status("resource-2") == ResourceStatus.ERROR

    def test_get_all_stats(self, coordinator):
        """Тест получения статистики всех ресурсов."""
        # Добавляем некоторую статистику
        coordinator.update_resource_stats(
            resource_id="resource-1",
            success=True,
            response_time=2.0,
            error_message=None,
            rate_limited=False,
        )

        coordinator.update_resource_stats(
            resource_id="resource-2",
            success=False,
            response_time=1.0,
            error_message="Timeout",
            rate_limited=False,
        )

        # Получаем статистику всех ресурсов
        all_stats = coordinator.get_all_stats()

        # Проверяем структуру
        assert isinstance(all_stats, dict)
        assert "resource-1" in all_stats
        assert "resource-2" in all_stats
        assert "resource-3" in all_stats

        # Проверяем данные для resource-1
        stats1 = all_stats["resource-1"]
        assert stats1.total_attempts == 1
        assert stats1.successful_attempts == 1
        assert stats1.success_rate == 1.0
        assert stats1.avg_response_time == 2.0

        # Проверяем данные для resource-2
        stats2 = all_stats["resource-2"]
        assert stats2.total_attempts == 1
        assert stats2.successful_attempts == 0
        assert stats2.success_rate == 0.0

    def test_reset_resource_stats(self, coordinator):
        """Тест сброса статистики ресурса."""
        resource_id = "resource-1"

        # Добавляем статистику
        coordinator.update_resource_stats(
            resource_id=resource_id,
            success=True,
            response_time=2.0,
            error_message=None,
            rate_limited=False,
        )

        # Проверяем, что статистика добавлена
        assert coordinator.resource_stats[resource_id].total_attempts == 1

        # Сбрасываем статистику
        coordinator.reset_resource_stats(resource_id)

        # Проверяем сброс
        stats = coordinator.resource_stats[resource_id]
        assert stats.total_attempts == 0
        assert stats.successful_attempts == 0
        assert stats.failed_attempts == 0
        assert stats.total_response_time == 0.0
        assert stats.error_count == 0

    def test_get_best_resources(self, coordinator):
        """Тест получения лучших ресурсов."""
        # Добавляем разную статистику для создания различий в оценках
        coordinator.update_resource_stats(
            resource_id="resource-1",
            success=True,
            response_time=1.0,
            error_message=None,
            rate_limited=False,
        )

        coordinator.update_resource_stats(
            resource_id="resource-2",
            success=False,
            response_time=2.0,
            error_message="Error",
            rate_limited=False,
        )

        # Получаем лучшие ресурсы
        best_resources = coordinator.get_best_resources(limit=2)

        # Проверяем результат
        assert len(best_resources) == 2
        assert "resource-1" in best_resources  # Должен быть первым (успешный)
        # resource-3 должен быть вторым (нет статистики, считается надежным)
        assert "resource-3" in best_resources or "resource-2" in best_resources


class TestSearchCoordinatorIntegration:
    """Интеграционные тесты SearchCoordinator."""

    @pytest.fixture
    def real_config_loader(self):
        """Реальный ConfigLoader с тестовой конфигурацией."""
        # Создаем временные конфигурационные файлы
        import tempfile
        import json
        import os

        temp_dir = tempfile.mkdtemp()

        # Создаем resources_config.json
        resources_config = {
            "resources": [
                {
                    "id": "test-web-1",
                    "name": "Тестовый веб-ресурс 1",
                    "type": "web",
                    "priority": 1,
                    "base_url": "https://test1.com",
                    "search_url_template": "https://test1.com/search?isbn={isbn}",
                    "selectors": [
                        {"label": "title", "pattern": "h1.title", "confidence": 0.9}
                    ],
                },
                {
                    "id": "test-api-1",
                    "name": "Тестовый API-ресурс 1",
                    "type": "api",
                    "priority": 2,
                    "base_url": "https://api.test.com",
                    "search_url_template": "https://api.test.com/books/{isbn}",
                    "api_endpoint": "https://api.test.com/books/{isbn}",
                    "field_mapping": {"title": "volumeInfo.title"},
                },
            ]
        }

        resources_path = os.path.join(temp_dir, "resources_config.json")
        with open(resources_path, "w", encoding="utf-8") as f:
            json.dump(resources_config, f, ensure_ascii=False, indent=2)

        # Создаем scraper_config.json
        scraper_config = {
            "enabled_resources": ["test-web-1", "test-api-1"],
            "max_concurrent_tasks": 3,
            "enable_debug_selectors": True,
        }

        scraper_path = os.path.join(temp_dir, "scraper_config.json")
        with open(scraper_path, "w", encoding="utf-8") as f:
            json.dump(scraper_config, f, ensure_ascii=False, indent=2)

        # Создаем ConfigLoader
        loader = ConfigLoader(config_dir=temp_dir)

        yield loader

        # Очистка
        import shutil

        shutil.rmtree(temp_dir)

    def test_integration_with_real_config(self, real_config_loader):
        """Тест интеграции с реальным ConfigLoader."""
        enabled_resources = ["test-web-1", "test-api-1"]
        coordinator = SearchCoordinator(
            config_loader=real_config_loader, enabled_resources=enabled_resources
        )

        # Проверяем инициализацию
        assert coordinator is not None
        assert len(coordinator.resource_stats) == 2
        assert "test-web-1" in coordinator.resource_stats
        assert "test-api-1" in coordinator.resource_stats

        # Проверяем выбор ресурса
        resource_id = coordinator.get_next_resource(
            task_isbn="9781234567890", tried_resources=set()
        )

        assert resource_id in ["test-web-1", "test-api-1"]

        # Проверяем обновление статистики
        coordinator.update_resource_stats(
            resource_id=resource_id,
            success=True,
            response_time=1.5,
            error_message=None,
            rate_limited=False,
        )

        # Проверяем статистику
        all_stats = coordinator.get_all_stats()
        assert resource_id in all_stats
        stats = all_stats[resource_id]
        assert stats.total_attempts == 1
        assert stats.successful_attempts == 1
        assert stats.success_rate == 1.0

        print(f"Интеграционный тест пройден: выбран ресурс {resource_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
