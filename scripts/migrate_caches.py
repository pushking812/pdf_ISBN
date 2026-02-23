#!/usr/bin/env python3
"""
Скрипт миграции данных из старых кэшей в новую архитектуру.

Мигрирует данные:
1. Из isbn_data_cache.json в новый формат кэша
2. Из pdf_isbn_cache.json в новый формат кэша
3. Проверяет согласованность данных
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Добавляем путь к корню проекта для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper_core.integration.dual_write import DualWriteCacheManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_isbn_cache(
    old_cache_path: str = "isbn_data_cache.json",
    new_cache_manager: Optional[DualWriteCacheManager] = None,
    backup: bool = True,
) -> Dict[str, Any]:
    """
    Мигрирует данные из старого ISBN кэша в новый формат.

    Args:
        old_cache_path: Путь к старому кэшу
        new_cache_manager: Менеджер dual-write (если None, создается новый)
        backup: Создавать ли резервную копию старого кэша

    Returns:
        Словарь со статистикой миграции
    """
    stats = {
        "old_cache_path": old_cache_path,
        "entries_processed": 0,
        "entries_migrated": 0,
        "errors": [],
        "backup_created": False,
    }

    # Проверяем существование старого кэша
    if not os.path.isfile(old_cache_path):
        stats["errors"].append(f"Старый кэш не найден: {old_cache_path}")
        return stats

    # Создаем резервную копию
    if backup:
        backup_path = f"{old_cache_path}.backup"
        try:
            import shutil

            shutil.copy2(old_cache_path, backup_path)
            stats["backup_created"] = True
            stats["backup_path"] = backup_path
            logger.info(f"Создана резервная копия: {backup_path}")
        except Exception as e:
            stats["errors"].append(f"Ошибка создания резервной копии: {e}")

    # Загружаем старый кэш
    try:
        with open(old_cache_path, "r", encoding="utf-8") as f:
            old_cache_data = json.load(f)

        # Проверяем версию
        if old_cache_data.get("version") != 1:
            stats["errors"].append(
                f"Несовместимая версия кэша: {old_cache_data.get('version')}"
            )
            return stats

        entries = old_cache_data.get("entries", {})
        stats["entries_processed"] = len(entries)

        # Создаем менеджер dual-write, если не предоставлен
        if new_cache_manager is None:
            new_cache_manager = DualWriteCacheManager(
                isbn_cache_path=old_cache_path,
                enable_dual_write=True,
            )

        # Мигрируем записи
        migrated_count = 0
        for isbn, book_data in entries.items():
            try:
                # Сохраняем через dual-write (это обновит существующий кэш)
                success = new_cache_manager.save_isbn_data(
                    isbn, book_data, only_if_complete=False
                )
                if success:
                    migrated_count += 1
                else:
                    stats["errors"].append(f"Не удалось сохранить ISBN {isbn}")
            except Exception as e:
                stats["errors"].append(f"Ошибка миграции ISBN {isbn}: {e}")

        stats["entries_migrated"] = migrated_count
        logger.info(f"Мигрировано {migrated_count} из {len(entries)} записей ISBN кэша")

    except Exception as e:
        stats["errors"].append(f"Ошибка загрузки старого кэша: {e}")

    return stats


def migrate_pdf_cache(
    old_cache_path: str = "pdf_isbn_cache.json",
    new_cache_manager: Optional[DualWriteCacheManager] = None,
    backup: bool = True,
) -> Dict[str, Any]:
    """
    Мигрирует данные из старого PDF кэша в новый формат.

    Args:
        old_cache_path: Путь к старому кэшу
        new_cache_manager: Менеджер dual-write (если None, создается новый)
        backup: Создавать ли резервную копию старого кэша

    Returns:
        Словарь со статистикой миграции
    """
    stats = {
        "old_cache_path": old_cache_path,
        "entries_processed": 0,
        "entries_migrated": 0,
        "errors": [],
        "backup_created": False,
    }

    # Проверяем существование старого кэша
    if not os.path.isfile(old_cache_path):
        stats["errors"].append(f"Старый PDF кэш не найден: {old_cache_path}")
        return stats

    # Создаем резервную копию
    if backup:
        backup_path = f"{old_cache_path}.backup"
        try:
            import shutil

            shutil.copy2(old_cache_path, backup_path)
            stats["backup_created"] = True
            stats["backup_path"] = backup_path
            logger.info(f"Создана резервная копия PDF кэша: {backup_path}")
        except Exception as e:
            stats["errors"].append(f"Ошибка создания резервной копии: {e}")

    # Загружаем старый кэш
    try:
        with open(old_cache_path, "r", encoding="utf-8") as f:
            old_cache_data = json.load(f)

        # Проверяем версию
        if old_cache_data.get("version") != 1:
            stats["errors"].append(
                f"Несовместимая версия PDF кэша: {old_cache_data.get('version')}"
            )
            return stats

        entries = old_cache_data.get("entries", {})
        stats["entries_processed"] = len(entries)

        # Создаем менеджер dual-write, если не предоставлен
        if new_cache_manager is None:
            new_cache_manager = DualWriteCacheManager(
                pdf_cache_path=old_cache_path,
                enable_dual_write=True,
            )

        # Мигрируем записи
        migrated_count = 0
        for pdf_key, pdf_data in entries.items():
            try:
                # Сохраняем через dual-write
                success = new_cache_manager.save_pdf_data(pdf_key, pdf_data)
                if success:
                    migrated_count += 1
                else:
                    stats["errors"].append(f"Не удалось сохранить PDF ключ {pdf_key}")
            except Exception as e:
                stats["errors"].append(f"Ошибка миграции PDF ключа {pdf_key}: {e}")

        stats["entries_migrated"] = migrated_count
        logger.info(f"Мигрировано {migrated_count} из {len(entries)} записей PDF кэша")

    except Exception as e:
        stats["errors"].append(f"Ошибка загрузки старого PDF кэша: {e}")

    return stats


def validate_cache_consistency(
    isbn_cache_path: str = "isbn_data_cache.json",
    pdf_cache_path: str = "pdf_isbn_cache.json",
) -> Dict[str, Any]:
    """
    Проверяет согласованность данных в кэшах.

    Args:
        isbn_cache_path: Путь к ISBN кэшу
        pdf_cache_path: Путь к PDF кэшу

    Returns:
        Словарь с результатами проверки
    """
    results = {
        "isbn_cache_exists": os.path.isfile(isbn_cache_path),
        "pdf_cache_exists": os.path.isfile(pdf_cache_path),
        "isbn_cache_stats": {},
        "pdf_cache_stats": {},
        "consistency_issues": [],
        "summary": {},
    }

    # Загружаем и анализируем ISBN кэш
    if results["isbn_cache_exists"]:
        try:
            with open(isbn_cache_path, "r", encoding="utf-8") as f:
                isbn_cache = json.load(f)

            entries = isbn_cache.get("entries", {})
            results["isbn_cache_stats"] = {
                "version": isbn_cache.get("version"),
                "entries_count": len(entries),
                "sample_entries": list(entries.keys())[:5] if entries else [],
            }

            # Проверяем структуру записей
            for isbn, data in list(entries.items())[:10]:  # Проверяем только первые 10
                if not isinstance(data, dict):
                    results["consistency_issues"].append(
                        f"Некорректная структура данных для ISBN {isbn}"
                    )
                    continue

                # Проверяем обязательные поля
                required_fields = ["title", "authors", "source"]
                for field in required_fields:
                    if field not in data:
                        results["consistency_issues"].append(
                            f"Отсутствует поле '{field}' для ISBN {isbn}"
                        )

        except Exception as e:
            results["consistency_issues"].append(f"Ошибка загрузки ISBN кэша: {e}")

    # Загружаем и анализируем PDF кэш
    if results["pdf_cache_exists"]:
        try:
            with open(pdf_cache_path, "r", encoding="utf-8") as f:
                pdf_cache = json.load(f)

            entries = pdf_cache.get("entries", {})
            results["pdf_cache_stats"] = {
                "version": pdf_cache.get("version"),
                "entries_count": len(entries),
                "sample_entries": list(entries.keys())[:5] if entries else [],
            }

            # Проверяем структуру записей
            for pdf_key, data in list(entries.items())[:10]:
                if not isinstance(data, dict):
                    results["consistency_issues"].append(
                        f"Некорректная структура данных для PDF ключа {pdf_key}"
                    )
                    continue

                # Проверяем обязательные поля
                required_fields = ["isbn", "source", "mtime", "size"]
                for field in required_fields:
                    if field not in data:
                        results["consistency_issues"].append(
                            f"Отсутствует поле '{field}' для PDF ключа {pdf_key}"
                        )

        except Exception as e:
            results["consistency_issues"].append(f"Ошибка загрузки PDF кэша: {e}")

    # Создаем сводку
    results["summary"] = {
        "total_issues": len(results["consistency_issues"]),
        "isbn_cache_entries": results["isbn_cache_stats"].get("entries_count", 0),
        "pdf_cache_entries": results["pdf_cache_stats"].get("entries_count", 0),
        "status": "OK" if len(results["consistency_issues"]) == 0 else "ISSUES",
    }

    return results


def print_migration_report(stats: Dict[str, Any], cache_type: str = "ISBN"):
    """Выводит отчет о миграции."""
    print(f"\n{'=' * 60}")
    print(f"ОТЧЕТ О МИГРАЦИИ {cache_type} КЭША")
    print(f"{'=' * 60}")

    print(f"Путь к кэшу: {stats.get('old_cache_path', 'N/A')}")
    print(f"Обработано записей: {stats.get('entries_processed', 0)}")
    print(f"Мигрировано записей: {stats.get('entries_migrated', 0)}")

    if stats.get("backup_created"):
        print(f"Резервная копия: {stats.get('backup_path', 'N/A')}")

    errors = stats.get("errors", [])
    if errors:
        print(f"\nОшибки ({len(errors)}):")
        for i, error in enumerate(errors[:10], 1):  # Показываем первые 10 ошибок
            print(f"  {i}. {error}")
        if len(errors) > 10:
            print(f"  ... и еще {len(errors) - 10} ошибок")
    else:
        print("\nОшибок не обнаружено.")

    print(f"{'=' * 60}")


def main():
    """Основная функция скрипта."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Миграция данных из старых кэшей в новую архитектуру"
    )
    parser.add_argument(
        "--isbn-cache",
        default="isbn_data_cache.json",
        help="Путь к старому ISBN кэшу (по умолчанию: isbn_data_cache.json)",
    )
    parser.add_argument(
        "--pdf-cache",
        default="pdf_isbn_cache.json",
        help="Путь к старому PDF кэшу (по умолчанию: pdf_isbn_cache.json)",
    )
    parser.add_argument(
        "--no-backup", action="store_true", help="Не создавать резервные копии"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Только проверить согласованность, не мигрировать",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("Начало миграции данных из старых кэшей...")

    # Проверяем согласованность
    print("\nПроверка согласованности кэшей...")
    consistency = validate_cache_consistency(args.isbn_cache, args.pdf_cache)

    print(
        f"ISBN кэш: {'существует' if consistency['isbn_cache_exists'] else 'не найден'}"
    )
    print(
        f"PDF кэш: {'существует' if consistency['pdf_cache_exists'] else 'не найден'}"
    )

    if consistency["consistency_issues"]:
        print(f"\nОбнаружено проблем: {len(consistency['consistency_issues'])}")
        for issue in consistency["consistency_issues"][:5]:
            print(f"  - {issue}")
        if len(consistency["consistency_issues"]) > 5:
            print(f"  ... и еще {len(consistency['consistency_issues']) - 5} проблем")
    else:
        print("\nПроблем с согласованностью не обнаружено.")

    if args.validate_only:
        print("\nРежим только проверки. Миграция не выполняется.")
        return

    # Запрашиваем подтверждение
    print("\n" + "=" * 60)
    response = input("Продолжить миграцию? (y/N): ").strip().lower()
    if response not in ["y", "yes", "д", "да"]:
        print("Миграция отменена.")
        return

    # Создаем общий менеджер dual-write
    cache_manager = DualWriteCacheManager(
        isbn_cache_path=args.isbn_cache,
        pdf_cache_path=args.pdf_cache,
        enable_dual_write=True,
    )

    # Мигрируем ISBN кэш
    print("\nМиграция ISBN кэша...")
    isbn_stats = migrate_isbn_cache(
        old_cache_path=args.isbn_cache,
        new_cache_manager=cache_manager,
        backup=not args.no_backup,
    )
    print_migration_report(isbn_stats, "ISBN")

    # Мигрируем PDF кэш
    print("\nМиграция PDF кэша...")
    pdf_stats = migrate_pdf_cache(
        old_cache_path=args.pdf_cache,
        new_cache_manager=cache_manager,
        backup=not args.no_backup,
    )
    print_migration_report(pdf_stats, "PDF")

    # Итоговый отчет
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 60)

    total_processed = isbn_stats.get("entries_processed", 0) + pdf_stats.get(
        "entries_processed", 0
    )
    total_migrated = isbn_stats.get("entries_migrated", 0) + pdf_stats.get(
        "entries_migrated", 0
    )
    total_errors = len(isbn_stats.get("errors", [])) + len(pdf_stats.get("errors", []))

    print(f"Всего обработано записей: {total_processed}")
    print(f"Всего мигрировано записей: {total_migrated}")
    print(f"Всего ошибок: {total_errors}")

    if total_errors == 0:
        print("\n✅ Миграция успешно завершена!")
    else:
        print(f"\n⚠️  Миграция завершена с ошибками ({total_errors})")
        print(
            "Рекомендуется проверить логи и при необходимости восстановить из резервных копий."
        )
