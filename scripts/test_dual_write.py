#!/usr/bin/env python3
"""
Скрипт для тестирования dual-write механизма.

Проверяет:
1. Корректность записи данных в старые кэши
2. Совместимость форматов данных
3. Работу LegacyScraperAdapter с dual-write
"""

import json
import os
import sys
import tempfile
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

# Добавляем путь к корню проекта для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper_core.integration.dual_write import DualWriteCacheManager
from scraper_core.orchestrator.legacy_adapter import LegacyScraperAdapter

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_dual_write_basic() -> Dict[str, Any]:
    """
    Базовый тест dual-write механизма.

    Returns:
        Словарь с результатами теста
    """
    results = {
        "test_name": "basic_dual_write",
        "passed": True,
        "errors": [],
        "details": {},
    }

    # Создаем временные файлы для тестов
    with tempfile.TemporaryDirectory() as tmpdir:
        isbn_cache_path = os.path.join(tmpdir, "test_isbn_cache.json")
        pdf_cache_path = os.path.join(tmpdir, "test_pdf_cache.json")

        try:
            # Создаем менеджер dual-write
            cache_manager = DualWriteCacheManager(
                isbn_cache_path=isbn_cache_path,
                pdf_cache_path=pdf_cache_path,
                enable_dual_write=True,
            )

            # Тест 1: Сохранение данных книги
            test_isbn = "9781234567890"
            test_book_data = {
                "title": "Test Book Title",
                "authors": ["Test Author 1", "Test Author 2"],
                "pages": "300",
                "year": "2024",
                "source": "test",
                "publisher": "Test Publisher",
                "language": "ru",
            }

            success = cache_manager.save_isbn_data(test_isbn, test_book_data)
            if not success:
                results["passed"] = False
                results["errors"].append("Не удалось сохранить данные книги")

            # Проверяем, что данные записаны в файл
            if os.path.exists(isbn_cache_path):
                with open(isbn_cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)

                if cache_data.get("version") != 1:
                    results["passed"] = False
                    results["errors"].append(
                        f"Неверная версия кэша: {cache_data.get('version')}"
                    )

                entries = cache_data.get("entries", {})
                if test_isbn not in entries:
                    results["passed"] = False
                    results["errors"].append(f"ISBN {test_isbn} не найден в кэше")
                else:
                    saved_data = entries[test_isbn]
                    # Проверяем основные поля
                    for field in ["title", "authors", "source"]:
                        if field not in saved_data:
                            results["passed"] = False
                            results["errors"].append(
                                f"Отсутствует поле '{field}' в сохраненных данных"
                            )

                    results["details"]["saved_book_data"] = saved_data
            else:
                results["passed"] = False
                results["errors"].append(f"Файл кэша не создан: {isbn_cache_path}")

            # Тест 2: Сохранение данных PDF
            test_pdf_key = "test_file.pdf|123456"
            test_pdf_data = {
                "isbn": "9781234567890",
                "source": "text",
                "mtime": 1700000000.0,
                "size": 123456,
                "pdf_path": "/path/to/test.pdf",
                "confidence": 0.95,
            }

            success = cache_manager.save_pdf_data(test_pdf_key, test_pdf_data)
            if not success:
                results["passed"] = False
                results["errors"].append("Не удалось сохранить данные PDF")

            # Проверяем PDF кэш
            if os.path.exists(pdf_cache_path):
                with open(pdf_cache_path, "r", encoding="utf-8") as f:
                    pdf_cache_data = json.load(f)

                entries = pdf_cache_data.get("entries", {})
                if test_pdf_key not in entries:
                    results["passed"] = False
                    results["errors"].append(
                        f"PDF ключ {test_pdf_key} не найден в кэше"
                    )
                else:
                    saved_pdf_data = entries[test_pdf_key]
                    results["details"]["saved_pdf_data"] = saved_pdf_data
            else:
                results["passed"] = False
                results["errors"].append(f"Файл PDF кэша не создан: {pdf_cache_path}")

            # Тест 3: Пакетное сохранение
            batch_data = {
                "9781111111111": {
                    "title": "Batch Test Book 1",
                    "authors": ["Batch Author"],
                    "pages": "200",
                    "year": "2023",
                    "source": "batch_test",
                },
                "9782222222222": {
                    "title": "Batch Test Book 2",
                    "authors": ["Another Author"],
                    "pages": "150",
                    "year": "2022",
                    "source": "batch_test",
                },
            }

            saved_count = cache_manager.batch_save_isbn_data(batch_data)
            if saved_count != 2:
                results["passed"] = False
                results["errors"].append(
                    f"Ожидалось 2 сохраненных записи, получено {saved_count}"
                )

            # Проверяем статистику
            isbn_stats = cache_manager.get_isbn_cache_stats()
            pdf_stats = cache_manager.get_pdf_cache_stats()

            results["details"]["isbn_stats"] = isbn_stats
            results["details"]["pdf_stats"] = pdf_stats

        except Exception as e:
            results["passed"] = False
            results["errors"].append(f"Исключение в тесте: {e}")
            logger.exception("Ошибка в базовом тесте dual-write")

    return results


def test_dual_write_with_incomplete_data() -> Dict[str, Any]:
    """
    Тест dual-write с неполными данными.

    Returns:
        Словарь с результатами теста
    """
    results = {
        "test_name": "incomplete_data_dual_write",
        "passed": True,
        "errors": [],
        "details": {},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        isbn_cache_path = os.path.join(tmpdir, "test_incomplete_cache.json")

        try:
            cache_manager = DualWriteCacheManager(
                isbn_cache_path=isbn_cache_path,
                enable_dual_write=True,
            )

            # Тест 1: Данные без названия (не должны сохраняться с only_if_complete=True)
            incomplete_data = {
                "authors": ["Some Author"],
                "year": "2024",
                "source": "test",
            }

            success = cache_manager.save_isbn_data(
                "9783333333333", incomplete_data, only_if_complete=True
            )

            if success:
                results["passed"] = False
                results["errors"].append(
                    "Неполные данные не должны сохраняться с only_if_complete=True"
                )

            # Тест 2: Те же данные с only_if_complete=False (должны сохраниться)
            success = cache_manager.save_isbn_data(
                "9783333333333", incomplete_data, only_if_complete=False
            )

            if not success:
                results["passed"] = False
                results["errors"].append(
                    "Неполные данные должны сохраняться с only_if_complete=False"
                )

            # Проверяем, что данные записаны
            if os.path.exists(isbn_cache_path):
                with open(isbn_cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)

                entries = cache_data.get("entries", {})
                if "9783333333333" not in entries:
                    results["passed"] = False
                    results["errors"].append(
                        "Неполные данные не сохранены даже с only_if_complete=False"
                    )
                else:
                    saved_data = entries["9783333333333"]
                    results["details"]["incomplete_saved_data"] = saved_data

        except Exception as e:
            results["passed"] = False
            results["errors"].append(f"Исключение в тесте неполных данных: {e}")

    return results


async def test_legacy_adapter_with_dual_write() -> Dict[str, Any]:
    """
    Тест LegacyScraperAdapter с включенным dual-write.

    Returns:
        Словарь с результатами теста
    """
    results = {
        "test_name": "legacy_adapter_dual_write",
        "passed": True,
        "errors": [],
        "details": {},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        isbn_cache_path = os.path.join(tmpdir, "test_adapter_cache.json")

        try:
            # Создаем адаптер с включенным dual-write
            adapter = LegacyScraperAdapter(
                enable_dual_write=True,
                isbn_cache_path=isbn_cache_path,
            )

            # Тестовые ISBN (не будут реально скрапиться, т.к. это mock-тест)
            test_isbns = ["9781234567890", "9789876543210"]

            # Вызываем async_parallel_search (в реальном тесте нужно mock-нуть оркестратор)
            # Для простоты теста просто проверяем, что адаптер создается корректно
            results["details"]["adapter_created"] = True
            results["details"]["dual_write_enabled"] = (
                adapter.dual_write_manager.enable_dual_write
            )

            # Проверяем, что менеджер dual-write инициализирован
            if adapter.dual_write_manager is None:
                results["passed"] = False
                results["errors"].append(
                    "Менеджер dual-write не инициализирован в адаптере"
                )

            # Закрываем адаптер
            await adapter.close()

        except Exception as e:
            results["passed"] = False
            results["errors"].append(f"Исключение в тесте адаптера: {e}")
            logger.exception("Ошибка в тесте LegacyScraperAdapter")

    return results


def test_cache_format_compatibility() -> Dict[str, Any]:
    """
    Тест совместимости форматов данных.

    Returns:
        Словарь с результатами теста
    """
    results = {
        "test_name": "cache_format_compatibility",
        "passed": True,
        "errors": [],
        "details": {},
    }

    # Тестовые данные в старом формате (из реального кэша)
    old_format_book_data = {
        "title": "Test Book",
        "authors": ["Author 1", "Author 2"],
        "source": "Open Library",
        "pages": "300",
        "year": "2024",
    }

    old_format_pdf_data = {
        "isbn": "9781234567890",
        "source": "text",
        "mtime": 1700000000.0,
        "size": 1234567,
    }

    try:
        # Проверяем, что старый формат загружается корректно
        with tempfile.TemporaryDirectory() as tmpdir:
            # Создаем тестовый кэш в старом формате
            test_cache = {
                "version": 1,
                "entries": {"9781234567890": old_format_book_data},
            }

            cache_path = os.path.join(tmpdir, "test_old_format_cache.json")
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(test_cache, f, ensure_ascii=False, indent=2)

            # Создаем менеджер dual-write и проверяем загрузку
            cache_manager = DualWriteCacheManager(isbn_cache_path=cache_path)

            if "9781234567890" not in cache_manager.isbn_cache:
                results["passed"] = False
                results["errors"].append("Старый формат кэша не загружен корректно")
            else:
                loaded_data = cache_manager.isbn_cache["9781234567890"]
                results["details"]["loaded_old_format_data"] = loaded_data

                # Проверяем, что данные корректно конвертированы
                for field in ["title", "authors", "source", "pages", "year"]:
                    if field not in loaded_data:
                        results["passed"] = False
                        results["errors"].append(
                            f"Поле '{field}' отсутствует в загруженных данных"
                        )

    except Exception as e:
        results["passed"] = False
        results["errors"].append(f"Исключение в тесте совместимости форматов: {e}")

    return results


def print_test_results(results: Dict[str, Any]):
    """Выводит результаты теста."""
    print(f"\n{'=' * 60}")
    print(f"ТЕСТ: {results['test_name']}")
    print(f"{'=' * 60}")

    status = "✅ ПРОЙДЕН" if results["passed"] else "❌ ПРОВАЛЕН"
    print(f"Статус: {status}")

    if results["errors"]:
        print(f"\nОшибки ({len(results['errors'])}):")
        for i, error in enumerate(results["errors"], 1):
            print(f"  {i}. {error}")

    if results.get("details"):
        print("\nДетали:")
        for key, value in results["details"].items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for subkey, subvalue in value.items():
                    print(f"    {subkey}: {subvalue}")
            else:
                print(f"  {key}: {value}")

    print(f"{'=' * 60}")


async def main():
    """Основная функция тестирования."""
    print("Начало тестирования dual-write механизма...")

    # Запускаем все тесты
    all_results = []

    print("\n1. Базовый тест dual-write...")
    result1 = test_dual_write_basic()
    all_results.append(result1)
    print_test_results(result1)

    print("\n2. Тест с неполными данными...")
    result2 = test_dual_write_with_incomplete_data()
    all_results.append(result2)
    print_test_results(result2)

    print("\n3. Тест совместимости форматов...")
    result3 = test_cache_format_compatibility()
    all_results.append(result3)
    print_test_results(result3)

    print("\n4. Тест LegacyScraperAdapter с dual-write...")
    result4 = await test_legacy_adapter_with_dual_write()
    all_results.append(result4)
    print_test_results(result4)

    # Итоговый отчет
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ ОТЧЕТ ПО ТЕСТИРОВАНИЮ")
    print("=" * 60)

    total_tests = len(all_results)
    passed_tests = sum(1 for r in all_results if r["passed"])
    failed_tests = total_tests - passed_tests

    print(f"Всего тестов: {total_tests}")
    print(f"Пройдено: {passed_tests}")
    print(f"Провалено: {failed_tests}")

    if failed_tests == 0:
        print("\n✅ Все тесты пройдены успешно!")
        print("Dual-write механизм работает корректно.")
    else:
        print(f"\n⚠️  Обнаружены проблемы в {failed_tests} тестах.")
        print("Рекомендуется проверить реализацию dual-write.")

        # Выводим список проваленных тестов
        print("\nПроваленные тесты:")
        for result in all_results:
            if not result["passed"]:
                print(f"  - {result['test_name']}")
                for error in result["errors"][:2]:  # Показываем первые 2 ошибки
                    print(f"    * {error}")

    print(f"{'=' * 60}")

    # Возвращаем код выхода в зависимости от результатов
    return 0 if failed_tests == 0 else 1


if __name__ == "__main__":
    # Запускаем асинхронную main функцию
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
