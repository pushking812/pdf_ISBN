"""
Сборщик метрик производительности для системы скрапинга.

Предоставляет инструменты для сбора, агрегации и экспорта метрик
производительности системы в реальном времени.
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Типы собираемых метрик."""

    TIMING = "timing"
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class Metric:
    """Базовая метрика."""

    name: str
    type: MetricType
    value: Any
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует метрику в словарь."""
        return {
            "name": self.name,
            "type": self.type.value,
            "value": self.value,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "iso_timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
        }


@dataclass
class TimingStats:
    """Статистика времени выполнения."""

    count: int = 0
    total: float = 0.0
    min: float = float("inf")
    max: float = 0.0
    avg: float = 0.0

    def update(self, duration: float):
        """Обновляет статистику новым измерением."""
        self.count += 1
        self.total += duration

        if duration < self.min:
            self.min = duration

        if duration > self.max:
            self.max = duration

        self.avg = self.total / self.count if self.count > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует статистику в словарь."""
        return {
            "count": self.count,
            "total": self.total,
            "min": self.min,
            "max": self.max,
            "avg": self.avg,
        }


class MetricsCollector:
    """
    Основной класс для сбора метрик.

    Поддерживает:
    - Тайминги выполнения операций
    - Счетчики событий
    - Измерения значений (гаужи)
    - Гистограммы распределений
    """

    def __init__(self, enabled: bool = True):
        """
        Инициализация сборщика метрик.

        Args:
            enabled: Включен ли сбор метрик
        """
        self.enabled = enabled
        self.metrics: List[Metric] = []
        self.timings: Dict[str, TimingStats] = defaultdict(TimingStats)
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}

        # Контекстные теги по умолчанию
        self.default_tags = {"system": "scraper_core", "version": "1.0.0"}

    def timing(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """
        Записывает метрику времени выполнения.

        Args:
            name: Название метрики
            duration: Время выполнения в секундах
            tags: Дополнительные теги
        """
        if not self.enabled:
            return

        # Обновляем статистику
        self.timings[name].update(duration)

        # Сохраняем отдельную метрику
        metric_tags = self.default_tags.copy()
        if tags:
            metric_tags.update(tags)

        metric = Metric(
            name=name, type=MetricType.TIMING, value=duration, tags=metric_tags
        )
        self.metrics.append(metric)

    def increment(
        self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ):
        """
        Увеличивает счетчик.

        Args:
            name: Название счетчика
            value: Значение для увеличения
            tags: Дополнительные теги
        """
        if not self.enabled:
            return

        self.counters[name] += value

        metric_tags = self.default_tags.copy()
        if tags:
            metric_tags.update(tags)

        metric = Metric(
            name=name, type=MetricType.COUNTER, value=value, tags=metric_tags
        )
        self.metrics.append(metric)

    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """
        Устанавливает значение измерения.

        Args:
            name: Название измерения
            value: Значение
            tags: Дополнительные теги
        """
        if not self.enabled:
            return

        self.gauges[name] = value

        metric_tags = self.default_tags.copy()
        if tags:
            metric_tags.update(tags)

        metric = Metric(name=name, type=MetricType.GAUGE, value=value, tags=metric_tags)
        self.metrics.append(metric)

    def timeit(self, name: str, tags: Optional[Dict[str, str]] = None):
        """
        Декоратор/контекстный менеджер для измерения времени выполнения.

        Args:
            name: Название метрики
            tags: Дополнительные теги

        Returns:
            Контекстный менеджер
        """

        class TimingContext:
            def __init__(self, collector, name, tags):
                self.collector = collector
                self.name = name
                self.tags = tags
                self.start_time = None

            def __enter__(self):
                self.start_time = time.time()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                self.collector.timing(self.name, duration, self.tags)

            async def __aenter__(self):
                self.start_time = time.time()
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                self.collector.timing(self.name, duration, self.tags)

        return TimingContext(self, name, tags)

    def get_summary(self) -> Dict[str, Any]:
        """
        Возвращает сводку всех метрик.

        Returns:
            Словарь со сводкой метрик
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "timings": {name: stats.to_dict() for name, stats in self.timings.items()},
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "total_metrics": len(self.metrics),
        }

    def get_metrics(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Возвращает список всех собранных метрик.

        Args:
            limit: Ограничение количества возвращаемых метрик

        Returns:
            Список метрик в виде словарей
        """
        metrics_list = [metric.to_dict() for metric in self.metrics]

        if limit and limit > 0:
            return metrics_list[-limit:]

        return metrics_list

    def clear(self):
        """Очищает все собранные метрики."""
        self.metrics.clear()
        self.timings.clear()
        self.counters.clear()
        self.gauges.clear()

    def save_to_file(self, filepath: str):
        """
        Сохраняет метрики в файл.

        Args:
            filepath: Путь к файлу для сохранения
        """
        data = {
            "summary": self.get_summary(),
            "metrics": self.get_metrics(),
            "export_timestamp": datetime.now().isoformat(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Метрики сохранены в {filepath}")


# Глобальный экземпляр сборщика метрик
_global_collector = MetricsCollector(enabled=True)


def get_global_collector() -> MetricsCollector:
    """
    Возвращает глобальный экземпляр сборщика метрик.

    Returns:
        Глобальный сборщик метрик
    """
    return _global_collector


def timing(name: str, duration: float, tags: Optional[Dict[str, str]] = None):
    """
    Глобальная функция для записи метрики времени выполнения.

    Args:
        name: Название метрики
        duration: Время выполнения в секундах
        tags: Дополнительные теги
    """
    _global_collector.timing(name, duration, tags)


def increment(name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
    """
    Глобальная функция для увеличения счетчика.

    Args:
        name: Название счетчика
        value: Значение для увеличения
        tags: Дополнительные теги
    """
    _global_collector.increment(name, value, tags)


def gauge(name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """
    Глобальная функция для установки значения измерения.

    Args:
        name: Название измерения
        value: Значение
        tags: Дополнительные теги
    """
    _global_collector.gauge(name, value, tags)


def timeit(name: str, tags: Optional[Dict[str, str]] = None):
    """
    Глобальная функция для создания контекстного менеджера измерения времени.

    Args:
        name: Название метрики
        tags: Дополнительные теги

    Returns:
        Контекстный менеджер
    """
    return _global_collector.timeit(name, tags)


# Пример использования
if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(level=logging.INFO)

    collector = MetricsCollector()

    # Измерение времени выполнения
    with collector.timeit("test_operation"):
        time.sleep(0.1)

    # Увеличение счетчика
    collector.increment("requests_total")
    collector.increment("errors_total", tags={"type": "timeout"})

    # Установка измерения
    collector.gauge("memory_usage", 123.45)

    # Получение сводки
    summary = collector.get_summary()
    print("Сводка метрик:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # Сохранение в файл
    collector.save_to_file("test_metrics.json")
    print("\nМетрики сохранены в test_metrics.json")
