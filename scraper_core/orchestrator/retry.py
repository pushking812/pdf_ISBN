"""
Обработчик повторных попыток с экспоненциальным backoff.

Предоставляет стратегии обработки ошибок с повторными попытками,
экспоненциальным backoff и классификацией ошибок.
"""

import asyncio
import logging
import random
from typing import Callable, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Категории ошибок для стратегий повторных попыток."""

    NETWORK = "network"  # Сетевые ошибки (таймауты, соединение)
    RESOURCE = "resource"  # Ошибки ресурса (404, 503, блокировки)
    PARSING = "parsing"  # Ошибки парсинга (неверный формат, отсутствие данных)
    VALIDATION = "validation"  # Ошибки валидации (некорректные данные)
    UNKNOWN = "unknown"  # Неизвестные ошибки


@dataclass
class RetryConfig:
    """Конфигурация повторных попыток."""

    max_retries: int = 3  # Максимальное количество повторных попыток
    base_delay: float = 1.0  # Базовая задержка в секундах
    max_delay: float = 60.0  # Максимальная задержка в секундах
    jitter: float = 0.1  # Случайное отклонение задержки (0.0-1.0)
    exponential_base: float = 2.0  # Основание для экспоненциального backoff

    # Стратегии для разных категорий ошибок
    retry_network: bool = True  # Повторять при сетевых ошибках
    retry_resource: bool = True  # Повторять при ошибках ресурса
    retry_parsing: bool = False  # Повторять при ошибках парсинга
    retry_validation: bool = False  # Повторять при ошибках валидации
    retry_unknown: bool = True  # Повторять при неизвестных ошибках

    # Расширенные стратегии для разных категорий ошибок
    category_specific_config: Dict[ErrorCategory, Dict[str, Any]] = None

    # Дополнительные параметры
    timeout: Optional[float] = None  # Таймаут для операции
    circuit_breaker_threshold: int = 5  # Порог для circuit breaker
    circuit_breaker_reset_time: float = 60.0  # Время сброса circuit breaker

    def __post_init__(self):
        """Инициализация category_specific_config по умолчанию."""
        if self.category_specific_config is None:
            self.category_specific_config = {
                ErrorCategory.NETWORK: {"max_retries": 5, "base_delay": 2.0},
                ErrorCategory.RESOURCE: {"max_retries": 3, "base_delay": 3.0},
                ErrorCategory.PARSING: {"max_retries": 1, "base_delay": 1.0},
                ErrorCategory.VALIDATION: {"max_retries": 1, "base_delay": 1.0},
                ErrorCategory.UNKNOWN: {"max_retries": 2, "base_delay": 1.5},
            }


@dataclass
class RetryStats:
    """Статистика повторных попыток."""

    attempts: int = 0  # Общее количество попыток
    successes: int = 0  # Успешные попытки
    failures: int = 0  # Неудачные попытки
    total_delay: float = 0.0  # Общая задержка
    last_error: Optional[str] = None  # Последняя ошибка
    last_error_category: Optional[ErrorCategory] = None  # Категория последней ошибки


class CircuitBreaker:
    """Circuit breaker для предотвращения повторных запросов к неработающим ресурсам."""

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        name: str = "default",
    ):
        """
        Инициализация circuit breaker.

        Args:
            failure_threshold: Порог срабатывания (количество ошибок)
            reset_timeout: Время сброса в секундах
            name: Имя для логирования
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.name = name

        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def is_open(self) -> bool:
        """Проверка, открыт ли circuit breaker."""
        if self.state == "OPEN":
            # Проверяем, не истекло ли время сброса
            if self.last_failure_time:
                reset_time = self.last_failure_time + timedelta(
                    seconds=self.reset_timeout
                )
                if datetime.now() >= reset_time:
                    # Переходим в HALF_OPEN для тестовой попытки
                    self.state = "HALF_OPEN"
                    logger.debug(f"Circuit breaker {self.name} перешел в HALF_OPEN")
                    return False
            return True
        return False

    def record_failure(self):
        """Запись неудачи."""
        self.failures += 1
        self.last_failure_time = datetime.now()

        if self.failures >= self.failure_threshold and self.state != "OPEN":
            self.state = "OPEN"
            logger.warning(
                f"Circuit breaker {self.name} открыт после {self.failures} ошибок"
            )

    def record_success(self):
        """Запись успеха."""
        self.failures = 0
        self.state = "CLOSED"
        logger.debug(f"Circuit breaker {self.name} закрыт после успешной операции")

    def can_execute(self) -> bool:
        """Можно ли выполнить операцию."""
        return not self.is_open()


class RetryHandler:
    """
    Обработчик повторных попыток с экспоненциальным backoff.

    Предоставляет:
    1. Экспоненциальный backoff с джиттером
    2. Классификацию ошибок
    3. Circuit breaker для ресурсов
    4. Статистику выполнения
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Инициализация обработчика повторных попыток.

        Args:
            config: Конфигурация повторных попыток
        """
        self.config = config or RetryConfig()
        self.stats = RetryStats()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        logger.info(
            f"RetryHandler инициализирован с max_retries={self.config.max_retries}"
        )

    def _classify_error(self, error: Exception) -> ErrorCategory:
        """
        Классификация ошибки.

        Args:
            error: Исключение для классификации

        Returns:
            Категория ошибки
        """
        error_str = str(error).lower()

        # Сетевые ошибки
        network_errors = [
            "timeout",
            "connection",
            "socket",
            "network",
            "connect",
            "timed out",
            "connection refused",
            "connection reset",
        ]
        for network_error in network_errors:
            if network_error in error_str:
                return ErrorCategory.NETWORK

        # Ошибки ресурса
        resource_errors = [
            "404",
            "503",
            "502",
            "500",
            "429",
            "403",
            "blocked",
            "captcha",
            "bot",
            "access denied",
            "rate limit",
        ]
        for resource_error in resource_errors:
            if resource_error in error_str:
                return ErrorCategory.RESOURCE

        # Ошибки парсинга
        parsing_errors = [
            "parse",
            "json",
            "xml",
            "html",
            "selector",
            "xpath",
            "element not found",
            "no such element",
        ]
        for parsing_error in parsing_errors:
            if parsing_error in error_str:
                return ErrorCategory.PARSING

        # Ошибки валидации
        validation_errors = ["validation", "invalid", "format", "type", "value"]
        for validation_error in validation_errors:
            if validation_error in error_str:
                return ErrorCategory.VALIDATION

        return ErrorCategory.UNKNOWN

    def _should_retry(self, error_category: ErrorCategory) -> bool:
        """
        Определение, нужно ли повторять попытку для данной категории ошибки.

        Args:
            error_category: Категория ошибки

        Returns:
            True если нужно повторять, False если нет
        """
        # Проверка базовых настроек
        if error_category == ErrorCategory.NETWORK:
            base_retry = self.config.retry_network
        elif error_category == ErrorCategory.RESOURCE:
            base_retry = self.config.retry_resource
        elif error_category == ErrorCategory.PARSING:
            base_retry = self.config.retry_parsing
        elif error_category == ErrorCategory.VALIDATION:
            base_retry = self.config.retry_validation
        else:
            base_retry = self.config.retry_unknown

        # Если базовая настройка False, не повторяем
        if not base_retry:
            return False

        # Проверяем category-specific конфигурацию
        category_config = self.config.category_specific_config.get(error_category, {})
        max_retries = category_config.get("max_retries", self.config.max_retries)

        # Если max_retries = 0, не повторяем
        return max_retries > 0

    def _calculate_delay(
        self, attempt: int, error_category: Optional[ErrorCategory] = None
    ) -> float:
        """
        Расчет задержки для попытки с экспоненциальным backoff и джиттером.

        Args:
            attempt: Номер попытки (начинается с 0)
            error_category: Категория ошибки (опционально)

        Returns:
            Задержка в секундах
        """
        # Используем category-specific конфигурацию если доступна
        base_delay = self.config.base_delay
        exponential_base = self.config.exponential_base
        max_delay = self.config.max_delay

        if error_category and error_category in self.config.category_specific_config:
            category_config = self.config.category_specific_config[error_category]
            base_delay = category_config.get("base_delay", base_delay)
            exponential_base = category_config.get("exponential_base", exponential_base)
            max_delay = category_config.get("max_delay", max_delay)

        # Экспоненциальный backoff: base_delay * (exponential_base ^ attempt)
        delay = base_delay * (exponential_base**attempt)

        # Ограничение максимальной задержки
        delay = min(delay, max_delay)

        # Добавление джиттера (случайного отклонения)
        if self.config.jitter > 0:
            jitter_amount = delay * self.config.jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0.1, delay)  # Минимальная задержка 0.1 секунды

        return delay

    def _get_max_retries_for_category(self, error_category: ErrorCategory) -> int:
        """
        Получение максимального количества повторных попыток для категории ошибки.

        Args:
            error_category: Категория ошибки

        Returns:
            Максимальное количество повторных попыток
        """
        if error_category in self.config.category_specific_config:
            category_config = self.config.category_specific_config[error_category]
            return category_config.get("max_retries", self.config.max_retries)
        return self.config.max_retries

    def get_circuit_breaker(self, resource_id: str) -> CircuitBreaker:
        """
        Получение или создание circuit breaker для ресурса.

        Args:
            resource_id: Идентификатор ресурса

        Returns:
            CircuitBreaker для ресурса
        """
        if resource_id not in self.circuit_breakers:
            self.circuit_breakers[resource_id] = CircuitBreaker(
                failure_threshold=self.config.circuit_breaker_threshold,
                reset_timeout=self.config.circuit_breaker_reset_time,
                name=f"resource_{resource_id}",
            )

        return self.circuit_breakers[resource_id]

    async def execute_with_retry(
        self, func: Callable, resource_id: str = "default", *args, **kwargs
    ) -> Any:
        """
        Выполнение функции с повторными попытками.

        Args:
            func: Функция для выполнения
            resource_id: Идентификатор ресурса (для circuit breaker)
            *args: Аргументы функции
            **kwargs: Ключевые аргументы функции

        Returns:
            Результат выполнения функции

        Raises:
            Exception: Если все попытки завершились неудачей
        """
        circuit_breaker = self.get_circuit_breaker(resource_id)

        # Проверка circuit breaker
        if not circuit_breaker.can_execute():
            raise Exception(f"Circuit breaker открыт для ресурса {resource_id}")

        last_error = None
        last_error_category = None

        # Определяем максимальное количество попыток на основе категории ошибки
        # (будет обновлено после первой ошибки)
        max_retries_for_category = self.config.max_retries

        for attempt in range(max_retries_for_category + 1):  # +1 для первой попытки
            try:
                # Выполнение функции
                if self.config.timeout:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs), timeout=self.config.timeout
                    )
                else:
                    result = await func(*args, **kwargs)

                # Успешное выполнение
                self.stats.successes += 1
                self.stats.attempts += 1
                circuit_breaker.record_success()

                logger.debug(
                    f"Успешное выполнение для ресурса {resource_id}, попытка {attempt + 1}"
                )
                return result

            except Exception as e:
                # Ошибка выполнения
                self.stats.failures += 1
                self.stats.attempts += 1
                self.stats.last_error = str(e)

                error_category = self._classify_error(e)
                self.stats.last_error_category = error_category

                last_error = e
                last_error_category = error_category

                circuit_breaker.record_failure()

                # Обновляем max_retries_for_category на основе категории ошибки
                max_retries_for_category = self._get_max_retries_for_category(
                    error_category
                )

                logger.warning(
                    f"Ошибка выполнения для ресурса {resource_id}, "
                    f"попытка {attempt + 1}/{max_retries_for_category + 1} "
                    f"(категория: {error_category.value}): {e}"
                )

                # Проверка, нужно ли повторять
                if attempt < max_retries_for_category and self._should_retry(
                    error_category
                ):
                    # Расчет и применение задержки с учетом категории ошибки
                    delay = self._calculate_delay(attempt, error_category)
                    self.stats.total_delay += delay

                    logger.debug(
                        f"Повтор через {delay:.2f} секунд для ресурса {resource_id}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Больше не повторяем
                    break

        # Все попытки завершились неудачей
        actual_max_retries = (
            max_retries_for_category if last_error_category else self.config.max_retries
        )
        error_msg = (
            f"Все {actual_max_retries + 1} попыток завершились неудачей "
            f"для ресурса {resource_id} (категория ошибки: {last_error_category.value if last_error_category else 'unknown'}). "
            f"Последняя ошибка: {last_error}"
        )
        logger.error(error_msg)
        raise last_error or Exception(error_msg)

    async def execute_sync_with_retry(
        self, func: Callable, resource_id: str = "default", *args, **kwargs
    ) -> Any:
        """
        Выполнение синхронной функции с повторными попытками.

        Args:
            func: Синхронная функция для выполнения
            resource_id: Идентификатор ресурса
            *args: Аргументы функции
            **kwargs: Ключевые аргументы функции

        Returns:
            Результат выполнения функции
        """

        async def async_wrapper():
            return func(*args, **kwargs)

        return await self.execute_with_retry(async_wrapper, resource_id)

    def get_stats(self) -> RetryStats:
        """Получение статистики выполнения."""
        return self.stats

    def reset_stats(self):
        """Сброс статистики."""
        self.stats = RetryStats()

    def reset_circuit_breaker(self, resource_id: str):
        """Сброс circuit breaker для ресурса."""
        if resource_id in self.circuit_breakers:
            self.circuit_breakers[resource_id] = CircuitBreaker(
                failure_threshold=self.config.circuit_breaker_threshold,
                reset_timeout=self.config.circuit_breaker_reset_time,
                name=f"resource_{resource_id}",
            )
            logger.debug(f"Circuit breaker сброшен для ресурса {resource_id}")
