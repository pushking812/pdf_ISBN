"""
Интеграция SelectorClient с системой конфигурации и обработчиками ресурсов.

Обеспечивает автоматическое обновление селекторов в конфигурации
на основе тестовых данных и результатов парсинга.
"""

import logging
from typing import Dict, List, Optional
from pathlib import Path

from scraper_core.config.loader import ConfigLoader
from scraper_core.config.base import SelectorPattern
from scraper_core.parsers.selector_client import SelectorClient

logger = logging.getLogger(__name__)


class SelectorIntegration:
    """Интеграция селекторов с системой конфигурации."""

    def __init__(self, config_dir: str = "config"):
        """
        Инициализация интеграции селекторов.

        Args:
            config_dir: Директория с конфигурационными файлами
        """
        self.config_dir = Path(config_dir)
        self.config_loader = ConfigLoader(config_dir)
        self.selector_client = SelectorClient({})

        # Загружаем конфигурацию
        self.env_config = self.config_loader.load_env_config()
        self.resources_config = self.config_loader.load_resources_config()

    def update_resource_selectors(
        self, resource_id: str, html: str, force_regenerate: bool = False
    ) -> List[SelectorPattern]:
        """
        Обновление селекторов для ресурса на основе HTML.

        Args:
            resource_id: Идентификатор ресурса
            html: HTML страницы для анализа
            force_regenerate: Принудительно перегенерировать все селекторы

        Returns:
            List[SelectorPattern]: Обновленные или новые селекторы
        """
        logger.info(f"Обновление селекторов для ресурса {resource_id}")

        resource = self.resources_config.get(resource_id)
        if not resource:
            logger.error(f"Ресурс {resource_id} не найден в конфигурации")
            return []

        if not resource.test_data or not resource.test_data.label_value_pairs:
            logger.warning(f"Нет тестовых данных для ресурса {resource_id}")
            return []

        label_value_pairs = resource.test_data.label_value_pairs
        updated_selectors = []

        # Для каждой пары метка-значение
        for label, expected_value in label_value_pairs.items():
            logger.debug(f"Обработка пары: {label} -> {expected_value}")

            # Ищем существующий селектор
            existing_selector = None
            for selector in resource.selectors:
                if selector.label == label:
                    existing_selector = selector
                    break

            if existing_selector and not force_regenerate:
                # Проверяем качество существующего селектора
                test_result = self.selector_client.extract_with_selectors(
                    html_or_driver=html,
                    selectors=[existing_selector],
                    use_selenium=False,
                )

                extracted_value = test_result.get(label)
                if extracted_value:
                    # Оцениваем качество
                    score = self._calculate_match_score(
                        extracted_value,
                        expected_value,
                        exact=True,
                        case_sensitive=False,
                    )

                    if score >= self.env_config.selector_confidence_threshold:
                        logger.debug(
                            f"Существующий селектор для {label} работает хорошо (оценка: {score})"
                        )
                        # Обновляем уверенность
                        existing_selector.confidence = score
                        # Проверяем, нет ли уже такого селектора в списке
                        if not any(
                            s.label == existing_selector.label
                            and s.pattern == existing_selector.pattern
                            for s in updated_selectors
                        ):
                            updated_selectors.append(existing_selector)
                        else:
                            logger.debug(
                                f"Селектор для {label} уже добавлен, пропускаем дублирование"
                            )
                        continue

            # Нужно сгенерировать новый селектор
            logger.info(f"Генерация нового селектора для {label}")

            # Генерируем селекторы для этой пары
            generated = self.selector_client.generate_selectors(
                html=html,
                label_value_pairs={label: expected_value},
                exact=True,
                case_sensitive=False,
                search_mode="both",
            )

            if generated:
                # Выбираем лучший селектор
                best_selector = self.selector_client.find_best_selector(
                    html=html,
                    label=label,
                    value=expected_value,
                    available_selectors=generated,
                    exact=True,
                    case_sensitive=False,
                )

                if best_selector:
                    # Обновляем уверенность на основе тестирования
                    test_result = self.selector_client.extract_with_selectors(
                        html_or_driver=html,
                        selectors=[best_selector],
                        use_selenium=False,
                    )

                    extracted_value = test_result.get(label)
                    if extracted_value:
                        score = self._calculate_match_score(
                            extracted_value,
                            expected_value,
                            exact=True,
                            case_sensitive=False,
                        )
                        best_selector.confidence = score

                    # Проверяем, нет ли уже такого селектора в списке
                    if not any(
                        s.label == best_selector.label
                        and s.pattern == best_selector.pattern
                        for s in updated_selectors
                    ):
                        updated_selectors.append(best_selector)
                        logger.info(
                            f"Сгенерирован новый селектор для {label} (оценка: {best_selector.confidence})"
                        )
                    else:
                        logger.debug(
                            f"Селектор для {label} уже добавлен, пропускаем дублирование"
                        )
                else:
                    logger.warning(f"Не удалось найти подходящий селектор для {label}")
            else:
                logger.warning(f"Не удалось сгенерировать селекторы для {label}")

        # Обновляем конфигурацию ресурса
        if updated_selectors:
            self._update_resource_config(resource_id, updated_selectors)

        return updated_selectors

    def auto_generate_all_selectors(self) -> Dict[str, List[SelectorPattern]]:
        """
        Автоматическая генерация селекторов для всех ресурсов с тестовыми данными.

        Returns:
            Dict[str, List[SelectorPattern]]: Сгенерированные селекторы по resource_id
        """
        logger.info("Автоматическая генерация селекторов для всех ресурсов")

        results = {}

        for resource_id, resource in self.resources_config.items():
            if not resource.test_data or not resource.test_data.label_value_pairs:
                logger.debug(f"Пропускаем ресурс {resource_id} (нет тестовых данных)")
                continue

            # Для реальной генерации нужен HTML страницы
            # В этом методе мы только планируем генерацию
            # Реальная генерация будет происходить при парсинге

            logger.info(f"Запланирована генерация селекторов для ресурса {resource_id}")
            results[resource_id] = []

        return results

    def migrate_existing_selectors(self) -> Dict[str, int]:
        """
        Миграция существующих селекторов из resources.py в новую систему.

        Returns:
            Dict[str, int]: Количество мигрированных селекторов по resource_id
        """
        logger.info("Миграция существующих селекторов из resources.py")

        try:
            import resources
            from config import ScraperConfig

            temp_config = ScraperConfig()
            resources_list = resources.get_scraper_resources(temp_config)

            migration_results = {}

            for resource_data in resources_list:
                resource_name = resource_data.get("name", "")
                resource_id = self._map_resource_name_to_id(resource_name)

                if not resource_id:
                    logger.warning(f"Неизвестный ресурс: {resource_name}, пропускаем")
                    continue

                resource = self.resources_config.get(resource_id)
                if not resource:
                    logger.warning(f"Ресурс {resource_id} не найден в конфигурации")
                    continue

                selectors_data = resource_data.get("selectors", {})
                migrated_count = 0

                for label, selector in selectors_data.items():
                    if not selector or selector.strip() == "":
                        continue

                    # Определяем тип селектора
                    pattern_type = "xpath"
                    if selector.startswith(".") or selector.startswith("#"):
                        pattern_type = "css"

                    # Добавляем селектор
                    success = self.config_loader.update_resource_selector(
                        resource_id=resource_id,
                        label=label,
                        pattern=selector,
                        pattern_type=pattern_type,
                        confidence=0.8,
                        generated=False,
                        source="resources.py",
                    )

                    if success:
                        migrated_count += 1
                        logger.debug(
                            f"Мигрирован селектор для {label} в ресурсе {resource_id}"
                        )

                if migrated_count > 0:
                    migration_results[resource_id] = migrated_count
                    logger.info(
                        f"Мигрировано {migrated_count} селекторов для ресурса {resource_id}"
                    )

            return migration_results

        except ImportError as e:
            logger.error(f"Ошибка импорта модулей для миграции: {e}")
            return {}
        except Exception as e:
            logger.error(f"Ошибка миграции селекторов: {e}")
            return {}

    def _update_resource_config(
        self, resource_id: str, selectors: List[SelectorPattern]
    ) -> bool:
        """
        Обновление конфигурации ресурса с новыми селекторами.

        Args:
            resource_id: Идентификатор ресурса
            selectors: Список селекторов для обновления

        Returns:
            bool: True если успешно обновлено
        """
        resource = self.resources_config.get(resource_id)
        if not resource:
            return False

        # Обновляем или добавляем селекторы
        for new_selector in selectors:
            existing_index = None
            for i, existing in enumerate(resource.selectors):
                if existing.label == new_selector.label:
                    existing_index = i
                    break

            if existing_index is not None:
                # Заменяем существующий селектор, если новый лучше
                existing = resource.selectors[existing_index]
                if new_selector.confidence > existing.confidence:
                    resource.selectors[existing_index] = new_selector
                    logger.debug(f"Обновлен селектор для {new_selector.label}")
            else:
                # Добавляем новый селектор
                resource.selectors.append(new_selector)
                logger.debug(f"Добавлен новый селектор для {new_selector.label}")

        # Сохраняем изменения
        self.resources_config[resource_id] = resource
        return self.config_loader._save_resources_config()

    def _calculate_match_score(
        self, extracted: str, expected: str, exact: bool, case_sensitive: bool
    ) -> float:
        """
        Вычисление оценки соответствия.

        Args:
            extracted: Извлеченное значение
            expected: Ожидаемое значение
            exact: Требовать точное совпадение
            case_sensitive: Учитывать регистр

        Returns:
            float: Оценка от 0.0 до 1.0
        """
        if not extracted or not expected:
            return 0.0

        extracted_norm = extracted.strip()
        expected_norm = expected.strip()

        if not case_sensitive:
            extracted_norm = extracted_norm.lower()
            expected_norm = expected_norm.lower()

        if exact:
            return 1.0 if extracted_norm == expected_norm else 0.0
        else:
            if expected_norm in extracted_norm:
                match_ratio = (
                    len(expected_norm) / len(extracted_norm) if extracted_norm else 0
                )
                return min(0.9, 0.5 + match_ratio * 0.4)
            else:
                return 0.0

    def _map_resource_name_to_id(self, resource_name: str) -> Optional[str]:
        """
        Маппинг названия ресурса из resources.py в ID в новой системе.

        Args:
            resource_name: Название ресурса

        Returns:
            Optional[str]: ID ресурса или None
        """
        mapping = {"Читай-город": "chitai_gorod", "Book.ru": "book_ru", "РГБ": "rsl"}
        return mapping.get(resource_name)
