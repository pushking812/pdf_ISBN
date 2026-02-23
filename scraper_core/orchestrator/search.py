"""
Координатор поиска для управления распределением задач между ресурсами.

SearchCoordinator отвечает за:
1. Приоритизацию ресурсов на основе истории успешности
2. Балансировку нагрузки между ресурсами
3. Выбор следующего ресурса для задачи
4. Отслеживание статистики выполнения
"""

import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from scraper_core.config.loader import ConfigLoader

logger = logging.getLogger(__name__)


class ResourceStatus(Enum):
    """Статус ресурса."""

    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class ResourceStats:
    """Статистика выполнения для ресурса."""

    resource_id: str
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    rate_limit_events: int = 0
    total_response_time: float = 0.0  # Суммарное время ответа в секундах
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0

    @property
    def success_rate(self) -> float:
        """Коэффициент успешности (0.0 - 1.0)."""
        if self.total_attempts == 0:
            return 1.0  # По умолчанию считаем ресурс надежным
        return self.successful_attempts / self.total_attempts

    @property
    def avg_response_time(self) -> float:
        """Среднее время ответа в секундах."""
        if self.successful_attempts == 0:
            return 0.0
        return self.total_response_time / self.successful_attempts

    @property
    def availability_score(self) -> float:
        """
        Оценка доступности ресурса (0.0 - 1.0).

        Учитывает:
        - Коэффициент успешности (вес 0.6)
        - Частоту ошибок (вес 0.2)
        - Время с последнего использования (вес 0.2)
        """
        success_score = self.success_rate * 0.6

        # Штраф за частые ошибки
        error_penalty = 0.0
        if self.total_attempts > 10:
            error_rate = self.error_count / self.total_attempts
            error_penalty = min(error_rate * 0.2, 0.2)

        # Бонус за недавнее использование (ресурс активен)
        recency_bonus = 0.0
        if self.last_used:
            hours_since_use = (datetime.now() - self.last_used).total_seconds() / 3600
            if hours_since_use < 1:  # Использовался менее часа назад
                recency_bonus = 0.2
            elif hours_since_use < 24:  # Использовался менее суток назад
                recency_bonus = 0.1

        return max(0.0, min(1.0, success_score - error_penalty + recency_bonus))


class SearchCoordinator:
    """Координатор поиска для управления распределением задач между ресурсами."""

    def __init__(
        self, config_loader: ConfigLoader, enabled_resources: Optional[List[str]] = None
    ):
        """
        Инициализация координатора поиска.

        Args:
            config_loader: Загрузчик конфигурации
            enabled_resources: Список включенных ресурсов (если None, берутся из конфигурации)
        """
        self.config_loader = config_loader
        self.resources_config = config_loader.load_resources_config()

        # Загружаем включенные ресурсы
        if enabled_resources is None:
            env_config = config_loader.load_env_config()
            self.enabled_resources = env_config.enabled_resources
        else:
            self.enabled_resources = enabled_resources

        # Инициализируем статистику для каждого ресурса
        self.resource_stats: Dict[str, ResourceStats] = {}
        self.resource_status: Dict[str, ResourceStatus] = {}

        for resource_id in self.enabled_resources:
            if resource_id in self.resources_config:
                self.resource_stats[resource_id] = ResourceStats(
                    resource_id=resource_id
                )
                self.resource_status[resource_id] = ResourceStatus.AVAILABLE

        logger.info(
            f"SearchCoordinator инициализирован с {len(self.resource_stats)} ресурсами"
        )

    def get_next_resource(
        self, task_isbn: str, tried_resources: Optional[Set[str]] = None
    ) -> Optional[str]:
        """
        Получить следующий ресурс для обработки задачи.

        Args:
            task_isbn: ISBN задачи (может использоваться для балансировки)
            tried_resources: Множество уже опробованных ресурсов для этой задачи

        Returns:
            Идентификатор ресурса или None, если нет доступных ресурсов
        """
        if tried_resources is None:
            tried_resources = set()

        # Фильтруем доступные ресурсы
        available_resources = []
        for resource_id in self.enabled_resources:
            if resource_id not in self.resources_config:
                continue
            if resource_id in tried_resources:
                continue
            if self.resource_status.get(resource_id) != ResourceStatus.AVAILABLE:
                continue
            available_resources.append(resource_id)

        if not available_resources:
            logger.warning(f"Нет доступных ресурсов для ISBN {task_isbn}")
            return None

        # Выбираем ресурс на основе стратегии приоритизации
        selected_resource = self._select_resource_by_strategy(
            available_resources, task_isbn
        )

        if selected_resource:
            logger.debug(f"Выбран ресурс {selected_resource} для ISBN {task_isbn}")

        return selected_resource

    def _select_resource_by_strategy(
        self, available_resources: List[str], task_isbn: str
    ) -> str:
        """
        Выбор ресурса по стратегии приоритизации.

        Стратегия: взвешенный случайный выбор с учетом:
        1. Оценки доступности ресурса (60%)
        2. Приоритета из конфигурации (20%)
        3. Балансировки нагрузки (20%)

        Args:
            available_resources: Список доступных ресурсов
            task_isbn: ISBN задачи (для детерминированной балансировки)

        Returns:
            Выбранный идентификатор ресурса
        """
        if len(available_resources) == 1:
            return available_resources[0]

        # Собираем веса для каждого ресурса
        weights = []
        for resource_id in available_resources:
            weight = 0.0

            # 1. Оценка доступности (0-60 баллов)
            stats = self.resource_stats.get(resource_id)
            if stats:
                weight += stats.availability_score * 60

            # 2. Приоритет из конфигурации (0-20 баллов)
            resource_config = self.resources_config.get(resource_id)
            if resource_config:
                priority = getattr(resource_config, "priority", 1)
                # Нормализуем приоритет: 1 -> 10 баллов, 2 -> 5 баллов, 3 -> 3 балла
                priority_score = {1: 20, 2: 10, 3: 5}.get(priority, 5)
                weight += priority_score

            # 3. Балансировка нагрузки (0-20 баллов)
            # Меньше использованные ресурсы получают больше баллов
            if stats and stats.total_attempts > 0:
                # Вычисляем относительную нагрузку
                max_attempts = max(
                    s.total_attempts
                    for s in self.resource_stats.values()
                    if s.total_attempts > 0
                )
                if max_attempts > 0:
                    load_ratio = stats.total_attempts / max_attempts
                    load_score = 20 * (
                        1 - load_ratio
                    )  # Меньше нагрузка -> больше баллов
                    weight += load_score
            else:
                # Ресурс еще не использовался - максимальный балл
                weight += 20

            weights.append(weight)

        # Нормализуем веса для вероятностного выбора
        total_weight = sum(weights)
        if total_weight == 0:
            # Равномерное распределение
            return available_resources[hash(task_isbn) % len(available_resources)]

        # Взвешенный случайный выбор
        import random

        selected = random.choices(available_resources, weights=weights, k=1)[0]
        return selected

    def update_resource_stats(
        self,
        resource_id: str,
        success: bool,
        response_time: Optional[float] = None,
        error_message: Optional[str] = None,
        rate_limited: bool = False,
    ) -> None:
        """
        Обновить статистику ресурса после выполнения задачи.

        Args:
            resource_id: Идентификатор ресурса
            success: Успешно ли выполнена задача
            response_time: Время выполнения в секундах
            error_message: Сообщение об ошибке (если есть)
            rate_limited: Была ли блокировка по rate limit
        """
        if resource_id not in self.resource_stats:
            self.resource_stats[resource_id] = ResourceStats(resource_id=resource_id)

        stats = self.resource_stats[resource_id]
        stats.total_attempts += 1
        stats.last_used = datetime.now()

        if success:
            stats.successful_attempts += 1
            if response_time:
                stats.total_response_time += response_time
        else:
            stats.failed_attempts += 1
            stats.error_count += 1
            if error_message:
                stats.last_error = error_message

        if rate_limited:
            stats.rate_limit_events += 1
            self.resource_status[resource_id] = ResourceStatus.RATE_LIMITED
            logger.warning(f"Ресурс {resource_id} заблокирован по rate limit")
        elif error_message and "timeout" in error_message.lower():
            # Временная ошибка, но ресурс остается доступным
            pass
        elif not success and stats.failed_attempts > 5:
            # Много ошибок подряд - временно отключаем ресурс
            self.resource_status[resource_id] = ResourceStatus.ERROR
            logger.warning(
                f"Ресурс {resource_id} временно отключен из-за множества ошибок"
            )

    def get_resource_status(self, resource_id: str) -> ResourceStatus:
        """
        Получить текущий статус ресурса.

        Args:
            resource_id: Идентификатор ресурса

        Returns:
            Текущий статус ресурса
        """
        return self.resource_status.get(resource_id, ResourceStatus.DISABLED)

    def set_resource_status(self, resource_id: str, status: ResourceStatus) -> None:
        """
        Установить статус ресурса.

        Args:
            resource_id: Идентификатор ресурса
            status: Новый статус
        """
        if resource_id in self.resource_status:
            self.resource_status[resource_id] = status
            logger.info(f"Статус ресурса {resource_id} изменен на {status.value}")

    def get_resource_stats(self, resource_id: str) -> Optional[ResourceStats]:
        """
        Получить статистику ресурса.

        Args:
            resource_id: Идентификатор ресурса

        Returns:
            Статистика ресурса или None, если ресурс не найден
        """
        return self.resource_stats.get(resource_id)

    def get_all_stats(self) -> Dict[str, ResourceStats]:
        """
        Получить статистику всех ресурсов.

        Returns:
            Словарь {resource_id: ResourceStats}
        """
        return self.resource_stats.copy()

    def reset_resource_stats(self, resource_id: str) -> None:
        """
        Сбросить статистику ресурса.

        Args:
            resource_id: Идентификатор ресурса
        """
        if resource_id in self.resource_stats:
            self.resource_stats[resource_id] = ResourceStats(resource_id=resource_id)
            logger.info(f"Статистика ресурса {resource_id} сброшена")

    def get_best_resources(self, limit: int = 3) -> List[str]:
        """
        Получить лучшие ресурсы на основе статистики.

        Args:
            limit: Максимальное количество возвращаемых ресурсов

        Returns:
            Список идентификаторов лучших ресурсов
        """
        if not self.resource_stats:
            return []

        # Сортируем ресурсы по оценке доступности
        sorted_resources = sorted(
            self.resource_stats.items(),
            key=lambda x: x[1].availability_score,
            reverse=True,
        )

        # Фильтруем только доступные ресурсы
        available_resources = [
            resource_id
            for resource_id, _ in sorted_resources
            if self.resource_status.get(resource_id) == ResourceStatus.AVAILABLE
        ]

        return available_resources[:limit]

    def should_retry_resource(
        self, resource_id: str, error_message: Optional[str] = None
    ) -> bool:
        """
        Определить, стоит ли повторять попытку с этим ресурсом.

        Args:
            resource_id: Идентификатор ресурса
            error_message: Сообщение об ошибке (если есть)

        Returns:
            True, если стоит повторить попытку
        """
        if resource_id not in self.resource_status:
            return False

        status = self.resource_status[resource_id]
        if status != ResourceStatus.AVAILABLE:
            return False

        # Проверяем, не было ли слишком много ошибок подряд
        stats = self.resource_stats.get(resource_id)
        if stats and stats.failed_attempts > 10:
            return False

        # Некоторые ошибки не требуют повторных попыток
        if error_message:
            error_lower = error_message.lower()
            if "not found" in error_lower or "404" in error_lower:
                return False  # Ресурс не найден - не повторяем
            if "blocked" in error_lower or "forbidden" in error_lower:
                return False  # Блокировка - не повторяем

        return True
