"""
Тесты для AntiBotHandler.
"""

import pytest
from unittest.mock import Mock

from scraper_core.orchestrator.antibot import (
    SimpleAntiBotHandler,
    AntiBotConfig,
    BlockType,
    BlockDetection,
    create_antibot_handler,
)


class TestAntiBotConfig:
    """Тесты конфигурации анти-бот обработчика."""

    def test_default_config(self):
        """Тест создания конфигурации с значениями по умолчанию."""
        config = AntiBotConfig()

        assert config.enable_proxy_rotation is False
        assert config.enable_user_agent_rotation is True
        assert config.enable_request_delays is True
        assert config.min_delay_seconds == 1.0
        assert config.max_delay_seconds == 3.0
        assert config.max_retries_on_block == 3
        assert config.captcha_solver_enabled is False
        assert config.proxy_list is None
        assert config.user_agent_list is None

    def test_custom_config(self):
        """Тест создания кастомной конфигурации."""
        config = AntiBotConfig(
            enable_proxy_rotation=True,
            enable_user_agent_rotation=False,
            enable_request_delays=False,
            min_delay_seconds=2.0,
            max_delay_seconds=5.0,
            max_retries_on_block=5,
            captcha_solver_enabled=True,
            proxy_list=["proxy1", "proxy2"],
            user_agent_list=["ua1", "ua2"],
        )

        assert config.enable_proxy_rotation is True
        assert config.enable_user_agent_rotation is False
        assert config.enable_request_delays is False
        assert config.min_delay_seconds == 2.0
        assert config.max_delay_seconds == 5.0
        assert config.max_retries_on_block == 5
        assert config.captcha_solver_enabled is True
        assert config.proxy_list == ["proxy1", "proxy2"]
        assert config.user_agent_list == ["ua1", "ua2"]


class TestBlockDetection:
    """Тесты обнаружения блокировок."""

    def test_block_detection_creation(self):
        """Тест создания объекта обнаружения блокировки."""
        detection = BlockDetection(
            block_type=BlockType.CAPTCHA,
            confidence=0.85,
            evidence=["Найдено ключевое слово: captcha"],
            suggested_action="Использовать сервис решения CAPTCHA",
        )

        assert detection.block_type == BlockType.CAPTCHA
        assert detection.confidence == 0.85
        assert detection.evidence == ["Найдено ключевое слово: captcha"]
        assert detection.suggested_action == "Использовать сервис решения CAPTCHA"

    def test_block_type_enum(self):
        """Тест перечисления типов блокировок."""
        assert BlockType.CAPTCHA.value == "captcha"
        assert BlockType.RATE_LIMIT.value == "rate_limit"
        assert BlockType.IP_BLOCK.value == "ip_block"
        assert BlockType.USER_AGENT_BLOCK.value == "user_agent_block"
        assert BlockType.JAVASCRIPT_CHALLENGE.value == "javascript_challenge"
        assert BlockType.UNKNOWN.value == "unknown"


class TestSimpleAntiBotHandler:
    """Тесты SimpleAntiBotHandler."""

    @pytest.fixture
    def antibot_handler(self):
        """Фикстура обработчика анти-бот защиты."""
        config = AntiBotConfig(
            enable_user_agent_rotation=True,
            enable_request_delays=False,  # Отключаем задержки для тестов
        )
        return SimpleAntiBotHandler(config)

    @pytest.fixture
    def mock_response_429(self):
        """Мок ответа с кодом 429 (Too Many Requests)."""
        response = Mock()
        response.status_code = 429
        return response

    @pytest.fixture
    def mock_response_403(self):
        """Мок ответа с кодом 403 (Forbidden)."""
        response = Mock()
        response.status_code = 403
        return response

    @pytest.mark.asyncio
    async def test_initialization(self, antibot_handler):
        """Тест инициализации обработчика."""
        assert antibot_handler.config.enable_user_agent_rotation is True
        assert antibot_handler.config.enable_request_delays is False
        assert len(antibot_handler.user_agents) > 0
        assert antibot_handler._current_user_agent is not None

        stats = antibot_handler.get_stats()
        assert stats["blocks_detected"] == 0
        assert stats["evasion_attempts"] == 0
        assert stats["successful_evasions"] == 0

    @pytest.mark.asyncio
    async def test_detect_block_rate_limit_http(
        self, antibot_handler, mock_response_429
    ):
        """Тест обнаружения rate limit по HTTP коду."""
        detection = await antibot_handler.detect_block(mock_response_429)

        assert detection is not None
        assert detection.block_type == BlockType.RATE_LIMIT
        assert detection.confidence >= 0.8
        assert "HTTP 429" in detection.evidence[0]

    @pytest.mark.asyncio
    async def test_detect_block_ip_block_http(self, antibot_handler, mock_response_403):
        """Тест обнаружения IP блокировки по HTTP коду."""
        detection = await antibot_handler.detect_block(mock_response_403)

        assert detection is not None
        assert detection.block_type == BlockType.IP_BLOCK
        assert detection.confidence >= 0.8
        assert "HTTP 403" in detection.evidence[0]

    @pytest.mark.asyncio
    async def test_detect_block_captcha_keyword(self, antibot_handler):
        """Тест обнаружения CAPTCHA по ключевым словам."""
        html_with_captcha = """
        <html>
            <body>
                <div>Please solve this captcha to continue</div>
                <div>Подтвердите что вы человек</div>
            </body>
        </html>
        """

        detection = await antibot_handler.detect_block(None, html_with_captcha)

        assert detection is not None
        assert detection.block_type == BlockType.CAPTCHA
        assert detection.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_detect_block_rate_limit_keyword(self, antibot_handler):
        """Тест обнаружения rate limit по ключевым словам."""
        html_with_rate_limit = """
        <html>
            <body>
                <div>Rate limit exceeded. Please try again later.</div>
                <div>Запросов слишком много, подождите</div>
            </body>
        </html>
        """

        detection = await antibot_handler.detect_block(None, html_with_rate_limit)

        assert detection is not None
        assert detection.block_type == BlockType.RATE_LIMIT
        assert detection.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_detect_no_block(self, antibot_handler):
        """Тест случая, когда блокировка не обнаружена."""
        normal_html = """
        <html>
            <body>
                <div>Welcome to our website</div>
                <div>Product information</div>
            </body>
        </html>
        """

        detection = await antibot_handler.detect_block(None, normal_html)

        assert detection is None

    @pytest.mark.asyncio
    async def test_apply_evasion_strategy_rate_limit(self, antibot_handler):
        """Тест применения стратегии обхода rate limit."""
        changes = await antibot_handler.apply_evasion_strategy(BlockType.RATE_LIMIT)

        assert "evasion_attempts" in antibot_handler.get_stats()
        assert antibot_handler.get_stats()["evasion_attempts"] == 1
        assert antibot_handler.get_stats()["successful_evasions"] == 1

        # Проверяем, что стратегия применена
        assert "increased_delays" in changes or "new_user_agent" in changes

    @pytest.mark.asyncio
    async def test_apply_evasion_strategy_captcha(self, antibot_handler):
        """Тест применения стратегии обхода CAPTCHA."""
        changes = await antibot_handler.apply_evasion_strategy(BlockType.CAPTCHA)

        assert antibot_handler.get_stats()["captcha_detections"] == 1
        assert antibot_handler.get_stats()["successful_evasions"] == 1

        # Проверяем, что стратегия применена
        assert "action" in changes
        assert changes["action"] == "captcha_detected"

    @pytest.mark.asyncio
    async def test_prepare_request_with_user_agent(self, antibot_handler):
        """Тест подготовки запроса с user-agent."""
        request_params = await antibot_handler.prepare_request()

        # Проверяем, что user-agent добавлен
        assert "headers" in request_params
        assert "User-Agent" in request_params["headers"]
        assert (
            request_params["headers"]["User-Agent"]
            == antibot_handler._current_user_agent
        )

    @pytest.mark.asyncio
    async def test_prepare_request_with_delays(self):
        """Тест подготовки запроса с задержками."""
        config = AntiBotConfig(
            enable_request_delays=True, min_delay_seconds=0.01, max_delay_seconds=0.02
        )
        handler = SimpleAntiBotHandler(config)

        import time

        start_time = time.time()
        request_params = await handler.prepare_request()
        elapsed_time = time.time() - start_time

        # Проверяем, что задержка применена
        assert elapsed_time >= 0.01
        assert "applied_delay" in request_params
        assert 0.01 <= request_params["applied_delay"] <= 0.02

    def test_rotate_user_agent(self, antibot_handler):
        """Тест ротации user-agent."""
        original_ua = antibot_handler._current_user_agent

        new_ua = antibot_handler._rotate_user_agent()

        assert new_ua != original_ua
        assert new_ua in antibot_handler.user_agents
        assert antibot_handler._current_user_agent == new_ua

    def test_get_stats(self, antibot_handler):
        """Тест получения статистики."""
        stats = antibot_handler.get_stats()

        assert "blocks_detected" in stats
        assert "evasion_attempts" in stats
        assert "successful_evasions" in stats
        assert "captcha_detections" in stats
        assert "rate_limit_detections" in stats
        assert "config" in stats


class TestAntiBotHandlerFactory:
    """Тесты фабрики обработчиков анти-бот защиты."""

    def test_create_simple_handler(self):
        """Тест создания простого обработчика."""
        handler = create_antibot_handler("simple")

        assert isinstance(handler, SimpleAntiBotHandler)

    def test_create_advanced_handler(self):
        """Тест создания расширенного обработчика (заглушка)."""
        handler = create_antibot_handler("advanced")

        from scraper_core.orchestrator.antibot import AdvancedAntiBotHandler

        assert isinstance(handler, AdvancedAntiBotHandler)

    def test_create_invalid_handler_type(self):
        """Тест создания обработчика с неверным типом."""
        with pytest.raises(ValueError, match="Неизвестный тип обработчика"):
            create_antibot_handler("invalid")


class TestIntegration:
    """Интеграционные тесты."""

    @pytest.mark.asyncio
    async def test_full_detection_and_evasion_cycle(self):
        """Тест полного цикла обнаружения и обхода блокировки."""
        config = AntiBotConfig(
            enable_user_agent_rotation=True, enable_request_delays=False
        )
        handler = SimpleAntiBotHandler(config)

        # Имитируем ответ с CAPTCHA
        html_with_captcha = "<div>Please solve captcha to continue</div>"

        # Обнаруживаем блокировку
        detection = await handler.detect_block(None, html_with_captcha)

        assert detection is not None
        assert detection.block_type == BlockType.CAPTCHA

        # Применяем стратегию обхода
        changes = await handler.apply_evasion_strategy(detection.block_type)

        # Проверяем, что стратегия применена
        assert "action" in changes
        assert changes["action"] == "captcha_detected"

        # Проверяем статистику
        stats = handler.get_stats()
        assert stats["blocks_detected"] == 1
        assert stats["evasion_attempts"] == 1
        assert stats["successful_evasions"] == 1
        assert stats["captcha_detections"] == 1

    @pytest.mark.asyncio
    async def test_multiple_block_detections(self):
        """Тест множественных обнаружений блокировок."""
        handler = SimpleAntiBotHandler(AntiBotConfig())

        # Обнаруживаем несколько типов блокировок
        html_captcha = "<div>captcha verification required</div>"
        html_rate_limit = "<div>rate limit exceeded</div>"

        detection1 = await handler.detect_block(None, html_captcha)
        detection2 = await handler.detect_block(None, html_rate_limit)

        assert detection1.block_type == BlockType.CAPTCHA
        assert detection2.block_type == BlockType.RATE_LIMIT

        stats = handler.get_stats()
        assert stats["captcha_detections"] == 1
        assert stats["rate_limit_detections"] == 1
