"""
Unit-тесты для RetryHandler.
"""

import asyncio
import pytest

from scraper_core.orchestrator.retry import (
    RetryHandler,
    RetryConfig,
    ErrorCategory,
    CircuitBreaker,
)


class TestRetryConfig:
    """Тесты конфигурации RetryConfig."""

    def test_default_config(self):
        """Тест значений по умолчанию."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.jitter == 0.1
        assert config.exponential_base == 2.0

        assert config.retry_network is True
        assert config.retry_resource is True
        assert config.retry_parsing is False
        assert config.retry_validation is False
        assert config.retry_unknown is True

        assert config.timeout is None
        assert config.circuit_breaker_threshold == 5
        assert config.circuit_breaker_reset_time == 60.0

        # Проверка category_specific_config
        assert ErrorCategory.NETWORK in config.category_specific_config
        assert ErrorCategory.RESOURCE in config.category_specific_config
        assert (
            config.category_specific_config[ErrorCategory.NETWORK]["max_retries"] == 5
        )

    def test_custom_config(self):
        """Тест пользовательской конфигурации."""
        config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
            retry_parsing=True,
            timeout=30.0,
        )

        assert config.max_retries == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0
        assert config.retry_parsing is True
        assert config.timeout == 30.0


class TestCircuitBreaker:
    """Тесты CircuitBreaker."""

    def test_initial_state(self):
        """Тест начального состояния."""
        cb = CircuitBreaker()

        assert cb.state == "CLOSED"
        assert cb.failures == 0
        assert cb.last_failure_time is None
        assert cb.is_open() is False
        assert cb.can_execute() is True

    def test_record_failure(self):
        """Тест записи неудачи."""
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        assert cb.failures == 1
        assert cb.state == "CLOSED"
        assert cb.is_open() is False

        cb.record_failure()
        cb.record_failure()
        assert cb.failures == 3
        assert cb.state == "OPEN"
        assert cb.is_open() is True
        assert cb.can_execute() is False

    def test_record_success(self):
        """Тест записи успеха."""
        cb = CircuitBreaker()
        cb.record_failure()
        cb.record_failure()

        assert cb.failures == 2
        assert cb.state == "CLOSED"

        cb.record_success()
        assert cb.failures == 0
        assert cb.state == "CLOSED"

    def test_reset_timeout(self):
        """Тест сброса по таймауту."""
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.1)

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "OPEN"
        assert cb.is_open() is True

        # Ждем сброса
        import time

        time.sleep(0.15)

        # После таймаута должен перейти в HALF_OPEN
        assert cb.is_open() is False
        assert cb.state == "HALF_OPEN"


class TestRetryHandler:
    """Тесты RetryHandler."""

    @pytest.fixture
    def retry_handler(self):
        """Фикстура RetryHandler."""
        return RetryHandler(RetryConfig(max_retries=2, base_delay=0.01))

    @pytest.fixture
    def mock_func_success(self):
        """Фикстура успешной функции."""

        async def success_func(*args, **kwargs):
            return "success"

        return success_func

    @pytest.fixture
    def mock_func_failure(self):
        """Фикстура функции, которая всегда падает."""

        async def failure_func(*args, **kwargs):
            raise Exception("test error")

        return failure_func

    @pytest.fixture
    def mock_func_success_after_retries(self):
        """Фикстура функции, которая успешна после нескольких попыток."""
        call_count = 0

        async def func(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception(f"attempt {call_count}")
            return "success"

        return func

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self, retry_handler, mock_func_success):
        """Тест успешного выполнения без повторных попыток."""
        result = await retry_handler.execute_with_retry(
            mock_func_success, "test_resource"
        )

        assert result == "success"
        stats = retry_handler.get_stats()
        assert stats.attempts == 1
        assert stats.successes == 1
        assert stats.failures == 0

    @pytest.mark.asyncio
    async def test_execute_with_retry_failure(self, retry_handler, mock_func_failure):
        """Тест неудачного выполнения с повторными попытками."""
        with pytest.raises(Exception, match="test error"):
            await retry_handler.execute_with_retry(mock_func_failure, "test_resource")

        stats = retry_handler.get_stats()
        # max_retries=2, значит всего попыток: 3 (первая + 2 повторные)
        assert stats.attempts == 3
        assert stats.successes == 0
        assert stats.failures == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_retries(
        self, retry_handler, mock_func_success_after_retries
    ):
        """Тест успешного выполнения после повторных попыток."""
        result = await retry_handler.execute_with_retry(
            mock_func_success_after_retries, "test_resource"
        )

        assert result == "success"
        stats = retry_handler.get_stats()
        assert stats.attempts == 3  # 2 неудачи + 1 успех
        assert stats.successes == 1
        assert stats.failures == 2

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, retry_handler, mock_func_failure):
        """Тест интеграции с CircuitBreaker."""
        # Вызываем функцию несколько раз, чтобы открыть circuit breaker
        for i in range(5):
            try:
                await retry_handler.execute_with_retry(
                    mock_func_failure, "test_resource"
                )
            except Exception:
                pass

        # Circuit breaker должен быть открыт
        cb = retry_handler.get_circuit_breaker("test_resource")
        assert cb.is_open() is True

        # Следующий вызов должен сразу падать с ошибкой circuit breaker
        with pytest.raises(Exception, match="Circuit breaker открыт"):
            await retry_handler.execute_with_retry(mock_func_failure, "test_resource")

    def test_error_classification(self, retry_handler):
        """Тест классификации ошибок."""
        # Сетевые ошибки
        network_error = Exception("Connection timeout")
        assert retry_handler._classify_error(network_error) == ErrorCategory.NETWORK

        # Ошибки ресурса
        resource_error = Exception("404 Not Found")
        assert retry_handler._classify_error(resource_error) == ErrorCategory.RESOURCE

        # Ошибки парсинга
        parsing_error = Exception("Failed to parse JSON")
        assert retry_handler._classify_error(parsing_error) == ErrorCategory.PARSING

        # Ошибки валидации
        validation_error = Exception("Invalid format")
        assert (
            retry_handler._classify_error(validation_error) == ErrorCategory.VALIDATION
        )

        # Неизвестные ошибки
        unknown_error = Exception("Some random error")
        assert retry_handler._classify_error(unknown_error) == ErrorCategory.UNKNOWN

    def test_should_retry(self, retry_handler):
        """Тест определения необходимости повторной попытки."""
        # Сетевые ошибки должны повторяться по умолчанию
        assert retry_handler._should_retry(ErrorCategory.NETWORK) is True

        # Ошибки парсинга не должны повторяться по умолчанию
        assert retry_handler._should_retry(ErrorCategory.PARSING) is False

        # Настраиваем конфигурацию
        config = RetryConfig(retry_parsing=True)
        handler = RetryHandler(config)
        assert handler._should_retry(ErrorCategory.PARSING) is True

    def test_calculate_delay(self, retry_handler):
        """Тест расчета задержки."""
        # Первая попытка (attempt=0) с base_delay=0.01
        # Но из-за минимальной задержки 0.1 и джиттера результат может быть 0.1
        # Вместо этого тестируем без джиттера
        config = RetryConfig(base_delay=0.01, jitter=0.0)
        handler = RetryHandler(config)
        delay1 = handler._calculate_delay(0)
        assert delay1 == pytest.approx(0.01, rel=0.1)  # base_delay

        # Вторая попытка (attempt=1) с exponential_base=2
        delay2 = handler._calculate_delay(1)
        assert delay2 == pytest.approx(0.02, rel=0.1)  # base_delay * 2

        # С джиттером
        config = RetryConfig(base_delay=1.0, jitter=0.5)
        handler = RetryHandler(config)
        delay = handler._calculate_delay(0)
        assert 0.5 <= delay <= 1.5  # 1.0 ± 0.5

    def test_get_max_retries_for_category(self, retry_handler):
        """Тест получения максимального количества попыток для категории."""
        # По умолчанию для NETWORK должно быть 5 (из category_specific_config)
        assert retry_handler._get_max_retries_for_category(ErrorCategory.NETWORK) == 5

        # Для RESOURCE должно быть 3
        assert retry_handler._get_max_retries_for_category(ErrorCategory.RESOURCE) == 3

        # Для неизвестной категории должно быть значение по умолчанию (max_retries=2 в фикстуре)
        assert retry_handler._get_max_retries_for_category(ErrorCategory.UNKNOWN) == 2

    @pytest.mark.asyncio
    async def test_execute_sync_with_retry(self, retry_handler):
        """Тест выполнения синхронной функции."""

        def sync_func(x, y):
            return x + y

        result = await retry_handler.execute_sync_with_retry(
            sync_func, "test_resource", 10, 20
        )

        assert result == 30
        stats = retry_handler.get_stats()
        assert stats.successes == 1

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Тест таймаута."""
        config = RetryConfig(timeout=0.1, max_retries=0)
        handler = RetryHandler(config)

        async def slow_func():
            await asyncio.sleep(0.2)
            return "too late"

        with pytest.raises(asyncio.TimeoutError):
            await handler.execute_with_retry(slow_func, "test_resource")

    @pytest.mark.asyncio
    async def test_reset_stats(self, retry_handler, mock_func_failure):
        """Тест сброса статистики."""
        # Выполняем несколько неудачных попыток
        try:
            await retry_handler.execute_with_retry(mock_func_failure, "test_resource")
        except Exception:
            pass  # Ожидаем ошибку

        stats_before = retry_handler.get_stats()
        assert stats_before.attempts > 0

        # Сбрасываем статистику
        retry_handler.reset_stats()

        stats_after = retry_handler.get_stats()
        assert stats_after.attempts == 0
        assert stats_after.successes == 0
        assert stats_after.failures == 0

    def test_reset_circuit_breaker(self, retry_handler, mock_func_failure):
        """Тест сброса circuit breaker."""
        # Открываем circuit breaker
        for i in range(5):
            try:
                asyncio.run(
                    retry_handler.execute_with_retry(mock_func_failure, "test_resource")
                )
            except Exception:
                pass

        cb = retry_handler.get_circuit_breaker("test_resource")
        assert cb.is_open() is True

        # Сбрасываем circuit breaker
        retry_handler.reset_circuit_breaker("test_resource")

        cb = retry_handler.get_circuit_breaker("test_resource")
        assert cb.is_open() is False
        assert cb.state == "CLOSED"
        assert cb.failures == 0


class TestErrorCategorySpecificConfig:
    """Тесты category-specific конфигурации."""

    def test_category_specific_retries(self):
        """Тест различного количества повторных попыток для разных категорий."""
        config = RetryConfig(
            max_retries=2,
            category_specific_config={
                ErrorCategory.NETWORK: {"max_retries": 5},
                ErrorCategory.RESOURCE: {"max_retries": 1},
            },
        )

        handler = RetryHandler(config)

        # Для NETWORK должно быть 5 попыток
        assert handler._get_max_retries_for_category(ErrorCategory.NETWORK) == 5

        # Для RESOURCE должно быть 1
        assert handler._get_max_retries_for_category(ErrorCategory.RESOURCE) == 1

        # Для других категорий - значение по умолчанию (2)
        assert handler._get_max_retries_for_category(ErrorCategory.PARSING) == 2

    def test_category_specific_delay(self):
        """Тест различных задержек для разных категорий."""
        config = RetryConfig(
            base_delay=1.0,
            category_specific_config={
                ErrorCategory.NETWORK: {"base_delay": 2.0, "exponential_base": 3.0},
                ErrorCategory.RESOURCE: {"base_delay": 0.5},
            },
        )

        handler = RetryHandler(config)

        # Для NETWORK
        delay = handler._calculate_delay(1, ErrorCategory.NETWORK)
        # 2.0 * (3.0 ^ 1) = 6.0
        assert delay == pytest.approx(6.0, rel=0.1)

        # Для RESOURCE
        delay = handler._calculate_delay(1, ErrorCategory.RESOURCE)
        # 0.5 * (2.0 ^ 1) = 1.0 (exponential_base берется из общей конфигурации)
        assert delay == pytest.approx(1.0, rel=0.1)

        # Для других категорий - общая задержка
        delay = handler._calculate_delay(1, ErrorCategory.PARSING)
        # 1.0 * (2.0 ^ 1) = 2.0
        assert delay == pytest.approx(2.0, rel=0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
