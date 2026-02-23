"""
Unit-тесты для TabManager.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from scraper_core.orchestrator.tabs import TabManager, TabInfo, TabState


class TestTabManager:
    """Тесты для класса TabManager."""

    @pytest.fixture
    def mock_driver(self):
        """Мок драйвера браузера."""
        driver = Mock()
        driver.current_window_handle = "handle_0"
        driver.switch_to.window = Mock()
        driver.switch_to.new_window = Mock()
        driver.get = Mock()
        driver.close = Mock()
        return driver

    @pytest.fixture
    def mock_search_coordinator(self):
        """Мок SearchCoordinator."""
        coordinator = Mock()
        coordinator.get_resource_config = Mock(
            return_value={
                "name": "test_resource",
                "base_url": "https://example.com",
                "search_url_template": "https://example.com/search?q={isbn}",
            }
        )
        return coordinator

    @pytest.fixture
    def mock_retry_handler(self):
        """Мок RetryHandler."""
        handler = Mock()
        handler.execute_with_retry = AsyncMock()
        return handler

    @pytest.fixture
    def tab_manager(self, mock_driver):
        """Экземпляр TabManager для тестирования."""
        manager = TabManager(max_tabs=3)
        manager.driver = mock_driver
        return manager

    @pytest.mark.asyncio
    async def test_initialization(self, tab_manager):
        """Тест инициализации TabManager."""
        assert tab_manager.max_tabs == 3
        assert tab_manager.tab_switch_delay == 0.2
        assert tab_manager.monitor_interval == 1.0
        assert tab_manager.load_balancing_threshold == 0.8
        assert tab_manager.tabs == {}
        assert tab_manager.is_running is False

    @pytest.mark.asyncio
    async def test_initialize_with_dependencies(
        self, tab_manager, mock_driver, mock_search_coordinator, mock_retry_handler
    ):
        """Тест инициализации с зависимостями."""
        with patch.object(tab_manager, "_create_initial_tabs") as mock_create:
            with patch.object(tab_manager, "_monitor_tabs") as mock_monitor:
                await tab_manager.initialize(
                    driver=mock_driver,
                    search_coordinator=mock_search_coordinator,
                    retry_handler=mock_retry_handler,
                )

        assert tab_manager.driver == mock_driver
        assert tab_manager.search_coordinator == mock_search_coordinator
        assert tab_manager.retry_handler == mock_retry_handler
        assert tab_manager.is_running is True

    @pytest.mark.asyncio
    async def test_create_initial_tabs(self, tab_manager, mock_driver):
        """Тест создания начальных вкладок."""
        # Настраиваем мок драйвера
        mock_driver.current_window_handle = "main_handle"
        mock_driver.switch_to.new_window.side_effect = [
            None,  # Первая вкладка
            None,  # Вторая вкладка
            Exception("Ошибка"),  # Третья вкладка (должна вызвать ошибку)
        ]

        # Вызываем создание вкладок
        await tab_manager._create_initial_tabs()

        # Проверяем, что созданы вкладки
        assert len(tab_manager.tabs) == 3  # Основная + 2 успешные
        assert "tab_0" in tab_manager.tabs
        assert "tab_1" in tab_manager.tabs
        assert "tab_2" in tab_manager.tabs

        # Проверяем состояние вкладок
        assert tab_manager.tabs["tab_0"].state == TabState.READY
        assert tab_manager.tabs["tab_0"].handle == "main_handle"

        # Проверяем вызовы драйвера
        assert mock_driver.switch_to.window.call_count >= 3
        assert mock_driver.switch_to.new_window.call_count == 3

    def test_find_free_tab(self, tab_manager):
        """Тест поиска свободной вкладки."""
        # Создаем тестовые вкладки
        tab_manager.tabs = {
            "tab_0": TabInfo(tab_id="tab_0", handle="handle_0", state=TabState.BUSY),
            "tab_1": TabInfo(tab_id="tab_1", handle="handle_1", state=TabState.READY),
            "tab_2": TabInfo(tab_id="tab_2", handle="handle_2", state=TabState.ERROR),
        }

        # Ищем свободную вкладку
        free_tab = tab_manager._find_free_tab()

        # Должна найтись вкладка в состоянии READY
        assert free_tab is not None
        assert free_tab.tab_id == "tab_1"
        assert free_tab.state == TabState.READY

    def test_find_free_tab_no_free(self, tab_manager):
        """Тест поиска свободной вкладки, когда все заняты."""
        # Создаем тестовые вкладки (все заняты)
        tab_manager.tabs = {
            "tab_0": TabInfo(tab_id="tab_0", handle="handle_0", state=TabState.BUSY),
            "tab_1": TabInfo(tab_id="tab_1", handle="handle_1", state=TabState.BUSY),
            "tab_2": TabInfo(tab_id="tab_2", handle="handle_2", state=TabState.ERROR),
        }

        # Ищем свободную вкладку
        free_tab = tab_manager._find_free_tab()

        # Не должна найтись свободная вкладка
        assert free_tab is None

    @pytest.mark.asyncio
    async def test_execute_task_on_tab(self, tab_manager, mock_driver):
        """Тест выполнения задачи на вкладке."""
        # Создаем тестовую вкладку
        tab = TabInfo(tab_id="test_tab", handle="test_handle", state=TabState.READY)

        # Создаем тестовую задачу
        task = {
            "task_id": "task_123",
            "isbn": "9781234567890",
            "resource_id": "test_resource",
        }

        # Мокаем методы
        with patch.object(tab_manager, "_perform_search") as mock_search:
            mock_search.return_value = {"success": True, "data": "test"}

            # Выполняем задачу
            result = await tab_manager._execute_task_on_tab(tab, task)

        # Проверяем результат
        assert result == {"success": True, "data": "test"}

        # Проверяем обновление состояния вкладки
        assert tab.state == TabState.COMPLETED
        assert tab.task_id == "task_123"
        assert tab.isbn == "9781234567890"
        assert tab.resource_id == "test_resource"
        assert tab.result == {"success": True, "data": "test"}
        assert tab.started_at is not None

        # Проверяем вызовы драйвера
        mock_driver.switch_to.window.assert_called_once_with("test_handle")

    @pytest.mark.asyncio
    async def test_execute_task_on_tab_error(self, tab_manager, mock_driver):
        """Тест выполнения задачи на вкладке с ошибкой."""
        # Создаем тестовую вкладку
        tab = TabInfo(tab_id="test_tab", handle="test_handle", state=TabState.READY)

        # Создаем тестовую задачу
        task = {"isbn": "9781234567890"}

        # Мокаем метод с ошибкой
        mock_driver.switch_to.window.side_effect = Exception("Ошибка переключения")

        # Выполняем задачу (должна вызвать исключение)
        with pytest.raises(Exception, match="Ошибка переключения"):
            await tab_manager._execute_task_on_tab(tab, task)

        # Проверяем обновление состояния вкладки
        assert tab.state == TabState.ERROR
        assert tab.error == "Ошибка переключения"

    @pytest.mark.asyncio
    async def test_perform_search(self, tab_manager):
        """Тест выполнения поиска на вкладке."""
        # Создаем тестовую вкладку
        tab = TabInfo(tab_id="test_tab", handle="test_handle")

        # Создаем тестовую задачу
        task = {"isbn": "9781234567890", "resource_id": "test_resource"}

        # Конфигурация ресурса
        resource_config = {"name": "Test Resource", "base_url": "https://example.com"}

        # Выполняем поиск
        result = await tab_manager._perform_search(tab, task, resource_config)

        # Проверяем результат
        assert result["isbn"] == "9781234567890"
        assert result["resource_id"] == "test_resource"
        assert result["success"] is True
        assert "title" in result
        assert "authors" in result
        assert "timestamp" in result
        assert result["tab_id"] == "test_tab"

    @pytest.mark.asyncio
    async def test_recover_tab(self, tab_manager, mock_driver):
        """Тест восстановления вкладки."""
        # Создаем тестовую вкладку с ошибкой
        tab = TabInfo(
            tab_id="test_tab",
            handle="test_handle",
            state=TabState.ERROR,
            error="Test error",
            result={"old": "data"},
            task_id="old_task",
            isbn="old_isbn",
            resource_id="old_resource",
            started_at=datetime.now(),
        )

        # Восстанавливаем вкладку
        await tab_manager._recover_tab(tab)

        # Проверяем, что состояние сброшено
        assert tab.state == TabState.READY
        assert tab.error is None
        assert tab.result is None
        assert tab.task_id is None
        assert tab.isbn is None
        assert tab.resource_id is None
        assert tab.started_at is None

        # Проверяем вызовы драйвера
        mock_driver.switch_to.window.assert_called_once_with("test_handle")
        mock_driver.get.assert_called_once_with("about:blank")

    @pytest.mark.asyncio
    async def test_recover_tab_error(self, tab_manager, mock_driver):
        """Тест восстановления вкладки с ошибкой."""
        # Создаем тестовую вкладку
        tab = TabInfo(tab_id="test_tab", handle="test_handle", state=TabState.ERROR)

        # Настраиваем мок с ошибкой
        mock_driver.switch_to.window.side_effect = Exception("Ошибка переключения")

        # Восстанавливаем вкладку
        await tab_manager._recover_tab(tab)

        # Проверяем, что вкладка осталась в состоянии ERROR
        assert tab.state == TabState.ERROR

    @pytest.mark.asyncio
    async def test_check_tab_health_timeout(self, tab_manager):
        """Тест проверки здоровья вкладки с таймаутом."""
        # Создаем тестовую вкладку с давним временем начала
        old_time = datetime(2023, 1, 1, 0, 0, 0)  # Очень старое время
        tab = TabInfo(
            tab_id="test_tab",
            handle="test_handle",
            state=TabState.BUSY,
            started_at=old_time,
        )
        tab_manager.tabs = {"test_tab": tab}

        # Мокаем восстановление
        with patch.object(tab_manager, "_recover_tab") as mock_recover:
            # Проверяем здоровье
            await tab_manager._check_tab_health()

        # Проверяем, что вкладка помечена как TIMEOUT
        assert tab.state == TabState.TIMEOUT

        # Проверяем, что вызвано восстановление
        mock_recover.assert_called_once_with(tab)

    @pytest.mark.asyncio
    async def test_balance_load(self, tab_manager, caplog):
        """Тест балансировки нагрузки."""
        # Создаем тестовые вкладки с высокой нагрузкой
        tab_manager.tabs = {
            "tab_0": TabInfo(tab_id="tab_0", handle="handle_0", state=TabState.BUSY),
            "tab_1": TabInfo(tab_id="tab_1", handle="handle_1", state=TabState.BUSY),
            "tab_2": TabInfo(tab_id="tab_2", handle="handle_2", state=TabState.BUSY),
            "tab_3": TabInfo(tab_id="tab_3", handle="handle_3", state=TabState.READY),
        }

        # Устанавливаем низкий порог для теста
        tab_manager.load_balancing_threshold = 0.5

        # Выполняем балансировку
        await tab_manager._balance_load()

        # Проверяем, что было предупреждение о высокой нагрузке
        assert "Высокая нагрузка на вкладки" in caplog.text

    def test_get_tab_status(self, tab_manager):
        """Тест получения статуса вкладок."""
        # Создаем тестовые вкладки
        start_time = datetime(2023, 1, 1, 0, 0, 0)
        tab_manager.tabs = {
            "tab_0": TabInfo(
                tab_id="tab_0",
                handle="handle_0",
                state=TabState.BUSY,
                task_id="task_123",
                isbn="9781234567890",
                resource_id="test_resource",
                started_at=start_time,
                error=None,
                result={"test": "data"},
            ),
            "tab_1": TabInfo(tab_id="tab_1", handle="handle_1", state=TabState.READY),
        }

        # Получаем статус
        status = tab_manager.get_tab_status()

        # Проверяем структуру статуса
        assert status["total_tabs"] == 2
        assert "tab_0" in status["tabs"]
        assert "tab_1" in status["tabs"]

        # Проверяем данные первой вкладки
        tab0_status = status["tabs"]["tab_0"]
        assert tab0_status["state"] == "busy"
        assert tab0_status["task_id"] == "task_123"
        assert tab0_status["isbn"] == "9781234567890"
        assert tab0_status["resource_id"] == "test_resource"
        assert tab0_status["started_at"] == start_time.isoformat()
        assert tab0_status["error"] is None
        assert tab0_status["has_result"] is True

    @pytest.mark.asyncio
    async def test_close(self, tab_manager, mock_driver):
        """Тест закрытия TabManager."""
        # Настраиваем состояние
        tab_manager.is_running = True
        tab_manager.monitor_task = asyncio.create_task(
            asyncio.sleep(3600)
        )  # Долгая задача
        tab_manager.tabs = {
            "tab_0": TabInfo(tab_id="tab_0", handle="main_handle"),
            "tab_1": TabInfo(tab_id="tab_1", handle="other_handle"),
        }

        # Закрываем менеджер
        await tab_manager.close()

        # Проверяем состояние
        assert tab_manager.is_running is False
        assert tab_manager.tabs == {}

        # Проверяем вызовы драйвера
        mock_driver.switch_to.window.assert_called()
        mock_driver.close.assert_called()


class TestTabManagerIntegration:
    """Интеграционные тесты TabManager."""

    @pytest.mark.asyncio
    async def test_execute_tasks_integration(self):
        """Интеграционный тест выполнения задач."""
        # Создаем TabManager с малым количеством вкладок
        manager = TabManager(max_tabs=2)

        # Мокаем драйвер
        mock_driver = Mock()
        mock_driver.current_window_handle = "main_handle"
        mock_driver.switch_to.window = Mock()
        mock_driver.switch_to.new_window = Mock()
        mock_driver.get = Mock()

        manager.driver = mock_driver

        # Создаем начальные вкладки
        with patch.object(manager, "_perform_search") as mock_search:
            mock_search.return_value = {"success": True}

            await manager._create_initial_tabs()

            # Создаем задачи
            tasks = [
                {"task_id": "1", "isbn": "9781111111111", "resource_id": "res1"},
                {"task_id": "2", "isbn": "9782222222222", "resource_id": "res2"},
                {"task_id": "3", "isbn": "9783333333333", "resource_id": "res3"},
            ]

            # Выполняем задачи
            results = await manager.execute_tasks(tasks)

            # Проверяем результаты
            assert len(results) == 3
            assert all(r["success"] for r in results)

            # Проверяем, что все вкладки освободились
            for tab in manager.tabs.values():
                assert tab.state == TabState.READY
