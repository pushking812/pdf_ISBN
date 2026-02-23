"""
Тесты для DriverManager.
"""

import pytest
from unittest.mock import Mock, patch

from scraper_core.orchestrator.drivers import (
    SimpleDriverManager,
    DriverConfig,
    DriverType,
    create_driver_manager,
)


class TestDriverConfig:
    """Тесты конфигурации драйвера."""

    def test_default_config(self):
        """Тест создания конфигурации с значениями по умолчанию."""
        config = DriverConfig()

        assert config.driver_type == DriverType.CHROME
        assert config.headless is True
        assert config.page_load_strategy == "eager"
        assert config.page_load_timeout == 20
        assert config.window_size == (1920, 1080)
        assert config.options is None
        assert config.capabilities is None

    def test_custom_config(self):
        """Тест создания кастомной конфигурации."""
        config = DriverConfig(
            driver_type=DriverType.CHROME,
            headless=False,
            page_load_strategy="normal",
            page_load_timeout=30,
            window_size=(1366, 768),
            options={"disable-gpu": True},
            capabilities={"browserName": "chrome"},
        )

        assert config.driver_type == DriverType.CHROME
        assert config.headless is False
        assert config.page_load_strategy == "normal"
        assert config.page_load_timeout == 30
        assert config.window_size == (1366, 768)
        assert config.options == {"disable-gpu": True}
        assert config.capabilities == {"browserName": "chrome"}


class TestSimpleDriverManager:
    """Тесты SimpleDriverManager."""

    @pytest.fixture
    def mock_driver(self):
        """Мок драйвера."""
        driver = Mock()
        driver.current_url = "about:blank"
        driver.quit = Mock()
        return driver

    @pytest.fixture
    def driver_manager(self):
        """Фикстура менеджера драйверов."""
        config = DriverConfig(headless=True)
        return SimpleDriverManager(config)

    @pytest.mark.asyncio
    async def test_initialization(self, driver_manager):
        """Тест инициализации менеджера драйверов."""
        assert driver_manager.config.headless is True
        assert driver_manager._drivers == []
        assert driver_manager._available_drivers == []
        assert driver_manager._in_use_drivers == {}

        stats = driver_manager.get_stats()
        assert stats["created"] == 0
        assert stats["reused"] == 0
        assert stats["total_drivers"] == 0

    @pytest.mark.asyncio
    @patch("scraper_core.orchestrator.drivers.uc")
    async def test_get_driver_creates_new(self, mock_uc, driver_manager, mock_driver):
        """Тест создания нового драйвера."""
        mock_uc.Chrome.return_value = mock_driver

        driver = await driver_manager.get_driver()

        assert driver == mock_driver
        assert len(driver_manager._drivers) == 1
        assert len(driver_manager._in_use_drivers) == 1

        stats = driver_manager.get_stats()
        assert stats["created"] == 1
        assert stats["reused"] == 0
        assert stats["total_drivers"] == 1

    @pytest.mark.asyncio
    @patch("scraper_core.orchestrator.drivers.uc")
    async def test_release_and_reuse_driver(self, mock_uc, driver_manager, mock_driver):
        """Тест освобождения и повторного использования драйвера."""
        mock_uc.Chrome.return_value = mock_driver

        # Получаем драйвер
        driver = await driver_manager.get_driver()

        # Освобождаем драйвер
        await driver_manager.release_driver(driver)

        assert len(driver_manager._available_drivers) == 1
        assert len(driver_manager._in_use_drivers) == 0

        # Получаем драйвер снова (должен быть переиспользован)
        driver2 = await driver_manager.get_driver()

        assert driver2 == driver
        stats = driver_manager.get_stats()
        assert stats["reused"] == 1

    @pytest.mark.asyncio
    async def test_cleanup(self, driver_manager, mock_driver):
        """Тест очистки всех драйверов."""
        # Добавляем мок драйверы
        driver_manager._drivers = [mock_driver, Mock()]
        driver_manager._available_drivers = [mock_driver]
        driver_manager._in_use_drivers = {"driver1": Mock()}

        # Вызываем cleanup
        await driver_manager.cleanup()

        # Проверяем, что все драйверы закрыты
        assert mock_driver.quit.called
        assert len(driver_manager._drivers) == 0
        assert len(driver_manager._available_drivers) == 0
        assert len(driver_manager._in_use_drivers) == 0

    @pytest.mark.asyncio
    async def test_get_stats(self, driver_manager):
        """Тест получения статистики."""
        stats = driver_manager.get_stats()

        assert "created" in stats
        assert "reused" in stats
        assert "cleaned" in stats
        assert "max_concurrent" in stats
        assert "total_drivers" in stats
        assert "available_drivers" in stats
        assert "in_use_drivers" in stats
        assert "config" in stats


class TestDriverManagerFactory:
    """Тесты фабрики менеджеров драйверов."""

    def test_create_simple_manager(self):
        """Тест создания простого менеджера."""
        manager = create_driver_manager("simple")

        assert isinstance(manager, SimpleDriverManager)

    def test_create_advanced_manager(self):
        """Тест создания расширенного менеджера (заглушка)."""
        manager = create_driver_manager("advanced", pool_size=3)

        from scraper_core.orchestrator.drivers import AdvancedDriverManager

        assert isinstance(manager, AdvancedDriverManager)
        assert manager.pool_size == 3

    def test_create_invalid_manager_type(self):
        """Тест создания менеджера с неверным типом."""
        with pytest.raises(ValueError, match="Неизвестный тип менеджера"):
            create_driver_manager("invalid")


class TestIntegration:
    """Интеграционные тесты."""

    @pytest.mark.asyncio
    async def test_driver_lifecycle(self):
        """Тест полного жизненного цикла драйвера."""
        config = DriverConfig(headless=True)
        manager = SimpleDriverManager(config)

        # Получаем статистику до создания драйверов
        initial_stats = manager.get_stats()
        assert initial_stats["created"] == 0
        assert initial_stats["total_drivers"] == 0

        # Создаем мок для драйвера, чтобы не запускать реальный Chrome
        with patch("scraper_core.orchestrator.drivers.uc") as mock_uc:
            mock_driver = Mock()
            mock_driver.current_url = "about:blank"
            mock_driver.quit = Mock()
            mock_uc.Chrome.return_value = mock_driver

            # Получаем драйвер
            driver = await manager.get_driver()

            # Проверяем статистику
            stats_after_get = manager.get_stats()
            assert stats_after_get["created"] == 1
            assert stats_after_get["total_drivers"] == 1
            assert stats_after_get["in_use_drivers"] == 1

            # Освобождаем драйвер
            await manager.release_driver(driver)

            # Проверяем статистику после освобождения
            stats_after_release = manager.get_stats()
            assert stats_after_release["in_use_drivers"] == 0
            assert stats_after_release["available_drivers"] == 1

            # Очищаем все
            await manager.cleanup()

            # Проверяем, что драйвер был закрыт
            assert mock_driver.quit.called

            final_stats = manager.get_stats()
            assert final_stats["total_drivers"] == 0
            assert final_stats["cleaned"] > 0
