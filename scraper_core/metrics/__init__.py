"""
Модуль для сбора и анализа метрик производительности системы скрапинга.

Предоставляет инструменты для мониторинга производительности, сбора статистики
и анализа работы системы в реальном времени.
"""

from .collector import (
    MetricsCollector,
    MetricType,
    Metric,
    TimingStats,
    get_global_collector,
    timing,
    increment,
    gauge,
    timeit,
)

__all__ = [
    "MetricsCollector",
    "MetricType",
    "Metric",
    "TimingStats",
    "get_global_collector",
    "timing",
    "increment",
    "gauge",
    "timeit",
]

__version__ = "1.0.0"