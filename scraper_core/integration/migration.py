"""
Скрипт миграции тестовых данных из debug_selectors.py в JSON-конфигурацию.

Этот модуль обеспечивает перенос существующих тестовых данных
и селекторов из модуля debug_selectors.py в новую систему конфигурации.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Добавляем путь к корню проекта для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scraper_core.config.loader import ConfigLoader
from scraper_core.config.base import TestData

logger = logging.getLogger(__name__)


def migrate_test_data_from_debug_selectors(
    config_dir: str = "config", debug_selectors_path: Optional[str] = None
) -> Dict[str, List[str]]:
    """
    Мигрировать тестовые данные из debug_selectors.py в JSON-конфигурацию.

    Args:
        config_dir: Директория с конфигурационными файлами
        debug_selectors_path: Путь к модулю debug_selectors.py

    Returns:
        Dict[str, List[str]]: Словарь с информацией о мигрированных данных
    """
    if debug_selectors_path is None:
        debug_selectors_path = "debug_selectors.py"

    results = {"migrated_resources": [], "test_data_added": [], "errors": []}

    try:
        # Импортируем модуль debug_selectors
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "debug_selectors", debug_selectors_path
        )
        if spec is None:
            raise ImportError(f"Не удалось загрузить модуль {debug_selectors_path}")

        debug_selectors = importlib.util.module_from_spec(spec)
        sys.modules["debug_selectors"] = debug_selectors
        spec.loader.exec_module(debug_selectors)

        logger.info(f"Модуль debug_selectors загружен из {debug_selectors_path}")

    except Exception as e:
        error_msg = f"Ошибка загрузки debug_selectors: {e}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
        return results

    # Инициализируем загрузчик конфигурации
    loader = ConfigLoader(config_dir)

    try:
        # Загружаем существующую конфигурацию
        env_config = loader.load_env_config()
        resources_config = loader.load_resources_config()

        logger.info(f"Загружено {len(resources_config)} ресурсов из конфигурации")

        # Получаем тестовые данные из debug_selectors
        test_data_func = getattr(debug_selectors, "get_test_data_to_parse", None)
        if not test_data_func:
            error_msg = "Функция get_test_data_to_parse не найдена в debug_selectors"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            return results

        test_data = test_data_func()
        logger.info(f"Получены тестовые данные для {len(test_data)} ресурсов")

        # Мигрируем данные для каждого ресурса
        for resource_id, test_cases in test_data.items():
            if not test_cases:
                logger.warning(f"Нет тестовых данных для ресурса {resource_id}")
                continue

            # Получаем конфигурацию ресурса
            resource = loader.get_resource_config(resource_id)
            if not resource:
                logger.warning(
                    f"Ресурс {resource_id} не найден в конфигурации, пропускаем"
                )
                continue

            # Берем первый тестовый случай (обычно самый репрезентативный)
            test_case = test_cases[0]
            url = test_case.get("url", "")

            # Извлекаем пары метка-значение
            label_value_pairs = {
                k: v
                for k, v in test_case.items()
                if k not in ["url", "html_fragment"] and v
            }

            if not label_value_pairs:
                logger.warning(f"Нет пар метка-значение для ресурса {resource_id}")
                continue

            # Создаем или обновляем тестовые данные
            if not resource.test_data:
                resource.test_data = TestData(
                    url=url, label_value_pairs=label_value_pairs
                )
                action = "добавлены"
            else:
                # Обновляем существующие данные
                resource.test_data.url = url
                resource.test_data.label_value_pairs.update(label_value_pairs)
                action = "обновлены"

            # Сохраняем изменения
            loader._resources_config[resource_id] = resource

            logger.info(
                f"Тестовые данные для ресурса {resource_id} {action}: "
                f"{len(label_value_pairs)} пар метка-значение"
            )

            results["migrated_resources"].append(resource_id)
            results["test_data_added"].append(
                f"{resource_id}: {len(label_value_pairs)} пар"
            )

        # Сохраняем обновленную конфигурацию
        if results["migrated_resources"]:
            success = loader._save_resources_config()
            if success:
                logger.info(
                    f"Конфигурация успешно сохранена. "
                    f"Мигрировано ресурсов: {len(results['migrated_resources'])}"
                )
            else:
                error_msg = "Ошибка сохранения конфигурации"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        else:
            logger.info("Нет данных для миграции")

        return results

    except Exception as e:
        error_msg = f"Ошибка миграции: {e}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
        return results


def migrate_selectors_from_resources_py(
    config_dir: str = "config", resources_py_path: Optional[str] = None
) -> Dict[str, List[str]]:
    """
    Мигрировать селекторы из resources.py в JSON-конфигурацию.

    Args:
        config_dir: Директория с конфигурационными файлами
        resources_py_path: Путь к модулю resources.py

    Returns:
        Dict[str, List[str]]: Словарь с информацией о мигрированных селекторах
    """
    if resources_py_path is None:
        resources_py_path = "resources.py"

    results = {"migrated_resources": [], "selectors_added": [], "errors": []}

    try:
        # Импортируем модуль resources
        import importlib.util

        spec = importlib.util.spec_from_file_location("resources", resources_py_path)
        if spec is None:
            raise ImportError(f"Не удалось загрузить модуль {resources_py_path}")

        resources_module = importlib.util.module_from_spec(spec)

        # Нам нужен доступ к config.py для создания ScraperConfig
        from config import ScraperConfig

        sys.modules["resources"] = resources_module
        spec.loader.exec_module(resources_module)

        logger.info(f"Модуль resources загружен из {resources_py_path}")

    except Exception as e:
        error_msg = f"Ошибка загрузки resources: {e}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
        return results

    # Инициализируем загрузчик конфигурации
    loader = ConfigLoader(config_dir)

    try:
        # Создаем временный конфиг для вызова функций ресурсов
        temp_config = ScraperConfig()

        # Получаем список ресурсов из resources.py
        get_resources_func = getattr(resources_module, "get_scraper_resources", None)
        if not get_resources_func:
            error_msg = "Функция get_scraper_resources не найдена в resources"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            return results

        resources_list = get_resources_func(temp_config)
        logger.info(f"Получено {len(resources_list)} ресурсов из resources.py")

        # Маппинг ID ресурсов
        resource_id_mapping = {
            "Читай-город": "chitai_gorod",
            "Book.ru": "book_ru",
            "РГБ": "rsl",
        }

        # Мигрируем селекторы для каждого ресурса
        for resource_data in resources_list:
            resource_name = resource_data.get("name", "")
            resource_id = resource_id_mapping.get(resource_name)

            if not resource_id:
                logger.warning(f"Неизвестный ресурс: {resource_name}, пропускаем")
                continue

            # Получаем конфигурацию ресурса
            resource = loader.get_resource_config(resource_id)
            if not resource:
                logger.warning(f"Ресурс {resource_id} не найден в конфигурации")
                continue

            # Извлекаем селекторы из resource_data
            selectors_data = resource_data.get("selectors", {})
            if not selectors_data:
                logger.info(f"Нет селекторов для ресурса {resource_id}")
                continue

            # Конвертируем селекторы в новый формат
            migrated_count = 0
            for label, selector in selectors_data.items():
                if not selector or selector.strip() == "":
                    continue

                # Определяем тип селектора
                pattern_type = "xpath"
                if selector.startswith(".") or selector.startswith("#"):
                    pattern_type = "css"

                # Добавляем селектор
                success = loader.update_resource_selector(
                    resource_id=resource_id,
                    label=label,
                    pattern=selector,
                    pattern_type=pattern_type,
                    confidence=0.8,  # Средняя уверенность для мигрированных селекторов
                    generated=False,
                    source="resources.py",
                )

                if success:
                    migrated_count += 1
                    logger.debug(
                        f"Мигрирован селектор для {label} в ресурсе {resource_id}"
                    )

            if migrated_count > 0:
                results["migrated_resources"].append(resource_id)
                results["selectors_added"].append(
                    f"{resource_id}: {migrated_count} селекторов"
                )
                logger.info(
                    f"Мигрировано {migrated_count} селекторов для ресурса {resource_id}"
                )

        # Сохраняем обновленную конфигурацию
        if results["migrated_resources"]:
            success = loader._save_resources_config()
            if success:
                logger.info(
                    f"Конфигурация селекторов успешно сохранена. "
                    f"Мигрировано ресурсов: {len(results['migrated_resources'])}"
                )
            else:
                error_msg = "Ошибка сохранения конфигурации селекторов"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        else:
            logger.info("Нет селекторов для миграции")

        return results

    except Exception as e:
        error_msg = f"Ошибка миграции селекторов: {e}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
        return results


def run_migration(
    config_dir: str = "config",
    migrate_test_data: bool = True,
    migrate_selectors: bool = True,
) -> Dict[str, Any]:
    """
    Запустить полную миграцию данных из старых модулей.

    Args:
        config_dir: Директория с конфигурационными файлами
        migrate_test_data: Мигрировать тестовые данные из debug_selectors
        migrate_selectors: Мигрировать селекторы из resources.py

    Returns:
        Dict[str, Any]: Сводные результаты миграции
    """
    logger.info("Запуск миграции данных в новую систему конфигурации")

    summary = {
        "test_data_migration": None,
        "selectors_migration": None,
        "total_resources_migrated": 0,
        "errors": [],
    }

    # Миграция тестовых данных
    if migrate_test_data:
        logger.info("Миграция тестовых данных из debug_selectors.py...")
        test_data_results = migrate_test_data_from_debug_selectors(config_dir)
        summary["test_data_migration"] = test_data_results

        if test_data_results["errors"]:
            summary["errors"].extend(test_data_results["errors"])

        logger.info(
            f"Тестовые данные мигрированы для {len(test_data_results['migrated_resources'])} ресурсов"
        )

    # Миграция селекторов
    if migrate_selectors:
        logger.info("Миграция селекторов из resources.py...")
        selectors_results = migrate_selectors_from_resources_py(config_dir)
        summary["selectors_migration"] = selectors_results

        if selectors_results["errors"]:
            summary["errors"].extend(selectors_results["errors"])

        logger.info(
            f"Селекторы мигрированы для {len(selectors_results['migrated_resources'])} ресурсов"
        )

    # Подсчитываем общее количество мигрированных ресурсов
    all_resources = set()
    if migrate_test_data and summary["test_data_migration"]:
        all_resources.update(summary["test_data_migration"]["migrated_resources"])
    if migrate_selectors and summary["selectors_migration"]:
        all_resources.update(summary["selectors_migration"]["migrated_resources"])

    summary["total_resources_migrated"] = len(all_resources)

    # Выводим сводку
    logger.info("=" * 60)
    logger.info("СВОДКА МИГРАЦИИ")
    logger.info("=" * 60)
    logger.info(f"Всего мигрировано ресурсов: {summary['total_resources_migrated']}")

    if migrate_test_data and summary["test_data_migration"]:
        test_data = summary["test_data_migration"]
        logger.info(f"Тестовые данные: {len(test_data['test_data_added'])} ресурсов")
        for item in test_data["test_data_added"]:
            logger.info(f"  - {item}")

    if migrate_selectors and summary["selectors_migration"]:
        selectors = summary["selectors_migration"]
        logger.info(f"Селекторы: {len(selectors['selectors_added'])} ресурсов")
        for item in selectors["selectors_added"]:
            logger.info(f"  - {item}")

    if summary["errors"]:
        logger.warning(f"Обнаружено ошибок: {len(summary['errors'])}")
        for error in summary["errors"]:
            logger.error(f"  - {error}")

    logger.info("=" * 60)

    return summary


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Запуск миграции
    print("Запуск миграции данных в новую систему конфигурации...")
    results = run_migration()

    if results["errors"]:
        print(f"\nМиграция завершена с ошибками: {len(results['errors'])}")
        sys.exit(1)
    else:
        print("\nМиграция успешно завершена!")
        print(f"Мигрировано ресурсов: {results['total_resources_migrated']}")
        sys.exit(0)
