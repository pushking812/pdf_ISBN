#!/usr/bin/env python3
"""
Скрипт для запуска A/B тестирования старой и новой архитектуры скрапинга.

Использует:
- ABTestRunner из scraper_core.integration.ab_testing
- MetricsCollector для сбора метрик
- Сохраняет результаты в JSON файл
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import List

# Добавляем путь к корню проекта для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper_core.integration.ab_testing import run_ab_test

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_isbns_from_file(filepath: str) -> List[str]:
    """
    Загружает список ISBN из файла.

    Args:
        filepath: Путь к файлу с ISBN

    Returns:
        Список ISBN
    """
    isbns = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    isbns.append(line)

        logger.info(f"Загружено {len(isbns)} ISBN из файла {filepath}")

    except FileNotFoundError:
        logger.error(f"Файл {filepath} не найден")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Ошибка при чтении файла {filepath}: {e}")
        sys.exit(1)

    return isbns


def generate_test_isbns(count: int) -> List[str]:
    """
    Генерирует тестовые ISBN.

    Args:
        count: Количество ISBN для генерации

    Returns:
        Список тестовых ISBN
    """
    # Используем реальные ISBN для тестирования
    base_isbns = [
        "9785171202448",  # Пример реального ISBN
        "9785171202449",
        "9785171202450",
        "9785171202451",
        "9785171202452",
        "9785171202453",
        "9785171202454",
        "9785171202455",
        "9785171202456",
        "9785171202457",
    ]

    if count <= len(base_isbns):
        return base_isbns[:count]

    # Генерируем дополнительные ISBN
    isbns = base_isbns.copy()
    for i in range(len(base_isbns), count):
        # Простая генерация тестовых ISBN (не реальных)
        isbn = f"97851712{10000 + i:05d}"
        isbns.append(isbn)

    return isbns


def print_results_summary(results):
    """
    Выводит сводку результатов тестирования.

    Args:
        results: Результаты A/B тестирования
    """
    print("\n" + "=" * 60)
    print("СВОДКА РЕЗУЛЬТАТОВ A/B ТЕСТИРОВАНИЯ")
    print("=" * 60)

    # Основные метрики
    legacy = results.legacy_metrics
    new = results.new_metrics
    comparison = results.comparison_metrics

    print("\n📊 ОБЩАЯ СТАТИСТИКА:")
    print(f"   Всего протестировано ISBN: {legacy.total_isbns}")
    print(f"   Время тестирования: {results.timestamp}")

    print("\n🏁 СТАРАЯ СИСТЕМА:")
    print(
        f"   Успешно: {legacy.successful_isbns} ({legacy.successful_isbns / legacy.total_isbns:.1%})"
    )
    print(f"   Ошибки: {legacy.failed_isbns} ({legacy.error_rate:.1%})")
    print(f"   Среднее время: {legacy.avg_time_per_isbn:.2f} сек")

    print("\n🚀 НОВАЯ СИСТЕМА:")
    print(
        f"   Успешно: {new.successful_isbns} ({new.successful_isbns / new.total_isbns:.1%})"
    )
    print(f"   Ошибки: {new.failed_isbns} ({new.error_rate:.1%})")
    print(f"   Среднее время: {new.avg_time_per_isbn:.2f} сек")

    print("\n📈 СРАВНЕНИЕ:")
    print(f"   Совпадение результатов: {comparison.get('match_rate', 0):.1%}")
    print(
        f"   Совпало результатов: {comparison.get('total_matches', 0)} из {comparison.get('total_tested', 0)}"
    )

    if comparison.get("performance_improvement", 0) > 0:
        improvement = comparison["performance_improvement"] * 100
        print(f"   Улучшение производительности: +{improvement:.1f}%")
    else:
        print(
            f"   Улучшение производительности: {comparison.get('performance_improvement', 0):.1%}"
        )

    # Детали по различиям
    differences = [r for r in results.detailed_results if not r.match]
    if differences:
        print(f"\n⚠️  РАЗЛИЧИЯ В РЕЗУЛЬТАТАХ ({len(differences)} ISBN):")
        for diff in differences[:5]:  # Показываем первые 5 различий
            print(f"   ISBN: {diff.isbn}")
            if diff.differences:
                for d in diff.differences[:2]:  # Показываем первые 2 различия
                    print(f"     - {d}")
            print()

        if len(differences) > 5:
            print(f"   ... и еще {len(differences) - 5} различий")

    print("\n" + "=" * 60)


async def main():
    """Основная функция скрипта."""
    parser = argparse.ArgumentParser(
        description="Запуск A/B тестирования старой и новой архитектуры скрапинга"
    )

    parser.add_argument(
        "--isbns",
        "-i",
        type=str,
        help="Список ISBN через запятую (например, '9785171202448,9785171202449')",
    )

    parser.add_argument(
        "--file",
        "-f",
        type=str,
        help="Путь к файлу со списком ISBN (по одному на строку)",
    )

    parser.add_argument(
        "--count",
        "-c",
        type=int,
        default=5,
        help="Количество тестовых ISBN для генерации (по умолчанию: 5)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="ab_test_results.json",
        help="Путь для сохранения результатов (по умолчанию: ab_test_results.json)",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")

    args = parser.parse_args()

    # Настройка уровня логирования
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Получаем список ISBN для тестирования
    isbns = []

    if args.isbns:
        isbns = [isbn.strip() for isbn in args.isbns.split(",") if isbn.strip()]
        logger.info(f"Используется {len(isbns)} ISBN из аргументов командной строки")

    elif args.file:
        isbns = load_isbns_from_file(args.file)

    else:
        isbns = generate_test_isbns(args.count)
        logger.info(f"Сгенерировано {len(isbns)} тестовых ISBN")

    if not isbns:
        logger.error("Не указаны ISBN для тестирования")
        parser.print_help()
        sys.exit(1)

    # Запускаем A/B тестирование
    logger.info(f"Начало A/B тестирования для {len(isbns)} ISBN...")

    try:
        results = await run_ab_test(isbns, args.output)

        # Выводим сводку
        print_results_summary(results)

        # Сохраняем результаты
        if args.output:
            logger.info(f"Результаты сохранены в {args.output}")

        # Проверяем успешность тестирования
        if results.comparison_metrics.get("match_rate", 0) < 0.8:
            logger.warning("Низкий процент совпадения результатов (<80%)")
            return 1

        logger.info("A/B тестирование завершено успешно")
        return 0

    except Exception as e:
        logger.error(f"Ошибка при выполнении A/B тестирования: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
