"""
Модуль для A/B тестирования старой и новой архитектуры скрапинга.

Предоставляет механизмы для параллельного запуска двух систем,
сбора метрик производительности и сравнения результатов.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class SystemType(Enum):
    """Тип системы для тестирования."""

    LEGACY = "legacy"
    NEW = "new"


@dataclass
class TestResult:
    """Результат тестирования для одного ISBN."""

    isbn: str
    legacy_data: Optional[Dict[str, Any]] = None
    new_data: Optional[Dict[str, Any]] = None
    legacy_error: Optional[str] = None
    new_error: Optional[str] = None
    legacy_time: float = 0.0
    new_time: float = 0.0
    match: bool = False
    differences: List[str] = field(default_factory=list)


@dataclass
class PerformanceMetrics:
    """Метрики производительности системы."""

    total_isbns: int = 0
    successful_isbns: int = 0
    failed_isbns: int = 0
    total_time: float = 0.0
    avg_time_per_isbn: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    error_rate: float = 0.0


@dataclass
class ABTestResults:
    """Результаты A/B тестирования."""

    legacy_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    new_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    comparison_metrics: Dict[str, Any] = field(default_factory=dict)
    detailed_results: List[TestResult] = field(default_factory=list)
    timestamp: str = ""


class ABTestRunner:
    """Запускает A/B тестирование старой и новой систем."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Инициализация раннера A/B тестирования.

        Args:
            config_path: Путь к конфигурационному файлу (опционально)
        """
        self.config_path = config_path
        self.results = ABTestResults()
        self.results.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    async def run_legacy_system(self, isbns: List[str]) -> Dict[str, Any]:
        """
        Запуск старой системы скрапинга.

        Args:
            isbns: Список ISBN для обработки

        Returns:
            Словарь с результатами
        """
        # TODO: Реализовать вызов старой системы через scraper.py
        # Временная заглушка для базовой структуры
        logger.info(f"Запуск старой системы для {len(isbns)} ISBN")

        # Имитация работы
        await asyncio.sleep(0.1)

        results = {}
        for isbn in isbns:
            results[isbn] = {
                "title": f"Тестовая книга {isbn}",
                "authors": ["Тестовый автор"],
                "price": "1000 руб.",
                "source": "legacy_stub",
            }

        return results

    async def run_new_system(self, isbns: List[str]) -> Dict[str, Any]:
        """
        Запуск новой системы скрапинга.

        Args:
            isbns: Список ISBN для обработки

        Returns:
            Словарь с результатами
        """
        # TODO: Реализовать вызов новой системы через LegacyScraperAdapter
        # Временная заглушка для базовой структуры
        logger.info(f"Запуск новой системы для {len(isbns)} ISBN")

        # Имитация работы
        await asyncio.sleep(0.05)  # Новая система быстрее

        results = {}
        for isbn in isbns:
            results[isbn] = {
                "title": f"Тестовая книга {isbn}",
                "authors": ["Тестовый автор"],
                "price": "1000 руб.",
                "source": "new_stub",
            }

        return results

    async def run_parallel_test(self, isbns: List[str]) -> ABTestResults:
        """
        Параллельный запуск обеих систем.

        Args:
            isbns: Список ISBN для тестирования

        Returns:
            Результаты A/B тестирования
        """
        logger.info(f"Начало A/B тестирования для {len(isbns)} ISBN")

        # Запускаем обе системы параллельно
        start_time = time.time()

        legacy_task = asyncio.create_task(self.run_legacy_system(isbns))
        new_task = asyncio.create_task(self.run_new_system(isbns))

        legacy_results, new_results = await asyncio.gather(
            legacy_task, new_task, return_exceptions=True
        )

        total_time = time.time() - start_time

        # Обрабатываем результаты
        self._process_results(isbns, legacy_results, new_results, total_time)

        logger.info(f"A/B тестирование завершено за {total_time:.2f} секунд")
        return self.results

    def _process_results(
        self,
        isbns: List[str],
        legacy_results: Dict[str, Any],
        new_results: Dict[str, Any],
        total_time: float,
    ):
        """Обработка и сравнение результатов."""
        self.results.detailed_results = []

        for isbn in isbns:
            legacy_data = (
                legacy_results.get(isbn) if isinstance(legacy_results, dict) else None
            )
            new_data = new_results.get(isbn) if isinstance(new_results, dict) else None

            # Сравниваем результаты
            match = self._compare_results(legacy_data, new_data)
            differences = self._find_differences(legacy_data, new_data)

            result = TestResult(
                isbn=isbn,
                legacy_data=legacy_data,
                new_data=new_data,
                legacy_error=None if legacy_data else "Ошибка в старой системе",
                new_error=None if new_data else "Ошибка в новой системе",
                match=match,
                differences=differences,
            )

            self.results.detailed_results.append(result)

        # Рассчитываем метрики
        self._calculate_metrics()

    def _compare_results(
        self, legacy_data: Optional[Dict], new_data: Optional[Dict]
    ) -> bool:
        """Сравнивает результаты двух систем."""
        if legacy_data is None and new_data is None:
            return True
        if legacy_data is None or new_data is None:
            return False

        # Базовая проверка совпадения ключевых полей
        key_fields = ["title", "authors", "price"]
        for field_name in key_fields:
            if legacy_data.get(field_name) != new_data.get(field_name):
                return False

        return True

    def _find_differences(
        self, legacy_data: Optional[Dict], new_data: Optional[Dict]
    ) -> List[str]:
        """Находит различия между результатами."""
        differences = []

        if legacy_data is None and new_data is None:
            return differences

        if legacy_data is None:
            differences.append("Старая система не вернула данных")
            return differences

        if new_data is None:
            differences.append("Новая система не вернула данных")
            return differences

        # Сравниваем ключевые поля
        key_fields = ["title", "authors", "price", "publisher", "year"]
        for field_name in key_fields:
            legacy_val = legacy_data.get(field_name)
            new_val = new_data.get(field_name)

            if legacy_val != new_val:
                differences.append(
                    f"Поле '{field_name}': старая='{legacy_val}', новая='{new_val}'"
                )

        return differences

    def _calculate_metrics(self):
        """Рассчитывает метрики производительности."""
        # TODO: Реализовать расчет реальных метрик на основе времени выполнения
        # Сейчас используем заглушки

        self.results.legacy_metrics = PerformanceMetrics(
            total_isbns=len(self.results.detailed_results),
            successful_isbns=sum(
                1 for r in self.results.detailed_results if r.legacy_data
            ),
            failed_isbns=sum(
                1 for r in self.results.detailed_results if not r.legacy_data
            ),
            avg_time_per_isbn=0.5,  # Заглушка
            error_rate=0.1,  # Заглушка
        )

        self.results.new_metrics = PerformanceMetrics(
            total_isbns=len(self.results.detailed_results),
            successful_isbns=sum(
                1 for r in self.results.detailed_results if r.new_data
            ),
            failed_isbns=sum(
                1 for r in self.results.detailed_results if not r.new_data
            ),
            avg_time_per_isbn=0.3,  # Заглушка
            error_rate=0.05,  # Заглушка
        )

        # Метрики сравнения
        total_matches = sum(1 for r in self.results.detailed_results if r.match)
        match_rate = (
            total_matches / len(self.results.detailed_results)
            if self.results.detailed_results
            else 0
        )

        self.results.comparison_metrics = {
            "match_rate": match_rate,
            "total_tested": len(self.results.detailed_results),
            "total_matches": total_matches,
            "total_differences": len(self.results.detailed_results) - total_matches,
            "performance_improvement": 0.4,  # Заглушка
        }

    def save_results(self, output_path: str):
        """
        Сохраняет результаты тестирования в файл.

        Args:
            output_path: Путь для сохранения результатов
        """
        results_dict = {
            "timestamp": self.results.timestamp,
            "legacy_metrics": self._metrics_to_dict(self.results.legacy_metrics),
            "new_metrics": self._metrics_to_dict(self.results.new_metrics),
            "comparison_metrics": self.results.comparison_metrics,
            "detailed_results": [
                {
                    "isbn": r.isbn,
                    "match": r.match,
                    "differences": r.differences,
                    "legacy_error": r.legacy_error,
                    "new_error": r.new_error,
                }
                for r in self.results.detailed_results
            ],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"Результаты сохранены в {output_path}")

    def _metrics_to_dict(self, metrics: PerformanceMetrics) -> Dict[str, Any]:
        """Преобразует метрики в словарь."""
        return {
            "total_isbns": metrics.total_isbns,
            "successful_isbns": metrics.successful_isbns,
            "failed_isbns": metrics.failed_isbns,
            "total_time": metrics.total_time,
            "avg_time_per_isbn": metrics.avg_time_per_isbn,
            "min_time": metrics.min_time,
            "max_time": metrics.max_time,
            "error_rate": metrics.error_rate,
        }


async def run_ab_test(
    isbns: List[str], output_path: Optional[str] = None
) -> ABTestResults:
    """
    Запускает A/B тестирование для списка ISBN.

    Args:
        isbns: Список ISBN для тестирования
        output_path: Путь для сохранения результатов (опционально)

    Returns:
        Результаты тестирования
    """
    runner = ABTestRunner()
    results = await runner.run_parallel_test(isbns)

    if output_path:
        runner.save_results(output_path)

    return results


if __name__ == "__main__":
    # Пример использования

    # Тестовые ISBN
    test_isbns = ["9785171202448", "9785171202449", "9785171202450"]

    # Запуск тестирования
    results = asyncio.run(run_ab_test(test_isbns, "ab_test_results.json"))

    print("Результаты A/B тестирования:")
    print(
        f"Совпадение результатов: {results.comparison_metrics.get('match_rate', 0):.2%}"
    )
    print(f"Протестировано ISBN: {len(results.detailed_results)}")
