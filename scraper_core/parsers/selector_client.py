"""
Клиент для работы с селекторами с интеграцией debug_selectors и html_fragment.

Обеспечивает генерацию и применение селекторов для извлечения данных
из HTML-страниц с использованием функционала debug_selectors.py
и html_fragment.py.
"""

import sys
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

# Добавляем путь к корню проекта для импорта существующих модулей
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from selenium.webdriver.remote.webdriver import WebDriver

from scraper_core.config.base import SelectorPattern

logger = logging.getLogger(__name__)


class SelectorClient:
    """Клиент для работы с селекторами с интеграцией debug_selectors."""

    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация клиента селекторов.

        Args:
            config: Конфигурация клиента
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.SelectorClient")

        # Ленивая загрузка модулей
        self._debug_selectors = None
        self._html_fragment = None

    @property
    def debug_selectors(self):
        """Ленивая загрузка модуля debug_selectors."""
        if self._debug_selectors is None:
            try:
                import debug_selectors

                self._debug_selectors = debug_selectors
                self.logger.debug("Модуль debug_selectors загружен")
            except ImportError as e:
                self.logger.error(f"Не удалось загрузить debug_selectors: {e}")
                self._debug_selectors = None
        return self._debug_selectors

    @property
    def html_fragment(self):
        """Ленивая загрузка модуля html_fragment."""
        if self._html_fragment is None:
            try:
                import html_fragment

                self._html_fragment = html_fragment
                self.logger.debug("Модуль html_fragment загружен")
            except ImportError as e:
                self.logger.error(f"Не удалось загрузить html_fragment: {e}")
                self._html_fragment = None
        return self._html_fragment

    def extract_with_selectors(
        self,
        html_or_driver: Union[str, WebDriver],
        selectors: List[SelectorPattern],
        use_selenium: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Извлечение данных с использованием селекторов.

        Args:
            html_or_driver: HTML-строка или WebDriver
            selectors: Список селекторов
            use_selenium: Использовать Selenium (определяется автоматически если None)

        Returns:
            Dict[str, Any]: Извлеченные данные
        """
        self.logger.debug(f"Извлечение данных с {len(selectors)} селекторами")

        if not self.debug_selectors:
            self.logger.error("Модуль debug_selectors не доступен")
            return {}

        result = {}

        for selector_pattern in selectors:
            label = selector_pattern.label
            pattern = selector_pattern.pattern
            pattern_type = selector_pattern.pattern_type

            # Конвертируем SelectorPattern в формат debug_selectors
            pattern_dict = {
                "type": pattern_type,
                "selector": pattern,
                "attribute": "text",  # По умолчанию извлекаем текст
                "label_text": label,
                "value_text": "",  # Не используется при извлечении
                "clean_regex": None,
                "resource_id": None,
            }

            try:
                # Используем extract_value из debug_selectors
                value = self.debug_selectors.extract_value(
                    html_or_driver=html_or_driver,
                    pattern=pattern_dict,
                    use_selenium=use_selenium,
                )

                if value:
                    result[label] = value
                    self.logger.debug(
                        f"Извлечено значение для {label}: {value[:50]}..."
                    )
                else:
                    self.logger.debug(f"Не удалось извлечь значение для {label}")

            except Exception as e:
                self.logger.error(f"Ошибка извлечения значения для {label}: {e}")

        return result

    def generate_selectors(
        self,
        html: str,
        label_value_pairs: Dict[str, str],
        exact: bool = True,
        case_sensitive: bool = False,
        search_mode: str = "both",
    ) -> List[SelectorPattern]:
        """
        Генерация селекторов на основе пар метка-значение.

        Args:
            html: HTML для анализа
            label_value_pairs: Пары метка-значение
            exact: Точное совпадение текста
            case_sensitive: Учитывать регистр
            search_mode: Режим поиска ('both', 'label_only', 'value_only')

        Returns:
            List[SelectorPattern]: Сгенерированные селекторы
        """
        self.logger.debug(f"Генерация селекторов для {len(label_value_pairs)} пар")

        if not self.debug_selectors or not self.html_fragment:
            self.logger.error("Модули debug_selectors или html_fragment не доступны")
            return []

        try:
            # Создаем mock args для debug_selectors

            class MockArgs:
                def __init__(self):
                    self.exact = exact
                    self.case_sensitive = case_sensitive
                    self.search_mode = search_mode
                    self.verbose = False
                    self.selenium = False

            args = MockArgs()

            # Для каждой пары метка-значение генерируем селекторы
            all_selectors = []

            for label, value in label_value_pairs.items():
                self.logger.debug(f"Генерация селектора для пары: {label} -> {value}")

                # Используем html_fragment для извлечения фрагментов
                fragments = self.html_fragment.extract_common_parent_html(
                    html=html,
                    label=label,
                    value=value,
                    exact_label=exact,
                    exact_value=exact,
                    case_sensitive=case_sensitive,
                    all_matches=True,
                    verbose=False,
                    search_mode=search_mode,
                )

                if not fragments:
                    self.logger.warning(
                        f"Не найдены фрагменты для пары: {label} -> {value}"
                    )
                    continue

                # Конвертируем фрагменты в формат для generate_pattern
                parse_frags = []
                for frag in fragments:
                    if isinstance(frag, tuple) and len(frag) >= 3:
                        label_text, value_text, html_fragment = (
                            frag[0],
                            frag[1],
                            frag[2],
                        )
                        parse_frags.append(
                            (label_text, value_text, html_fragment, [], None)
                        )

                if not parse_frags:
                    continue

                # Генерируем паттерны с помощью debug_selectors
                patterns = self.debug_selectors.generate_pattern(parse_frags, args)

                # Конвертируем паттерны в SelectorPattern
                for pattern in patterns:
                    selector = SelectorPattern(
                        label=label,
                        pattern=pattern.get("selector", ""),
                        pattern_type=pattern.get("type", "xpath"),
                        confidence=0.8,  # Средняя уверенность для сгенерированных селекторов
                        generated=True,
                        source="debug_selectors",
                    )
                    all_selectors.append(selector)

            self.logger.info(f"Сгенерировано {len(all_selectors)} селекторов")
            return all_selectors

        except Exception as e:
            self.logger.error(f"Ошибка генерации селекторов: {e}")
            return []

    def find_best_selector(
        self,
        html: str,
        label: str,
        value: str,
        available_selectors: List[SelectorPattern],
        exact: bool = True,
        case_sensitive: bool = False,
    ) -> Optional[SelectorPattern]:
        """
        Поиск лучшего селектора из доступных.

        Args:
            html: HTML для тестирования
            label: Метка поля
            value: Ожидаемое значение
            available_selectors: Доступные селекторы
            exact: Точное совпадение
            case_sensitive: Учитывать регистр

        Returns:
            Optional[SelectorPattern]: Лучший селектор или None
        """
        self.logger.debug(f"Поиск лучшего селектора для {label}")

        if not available_selectors:
            return None

        best_selector = None
        best_score = 0

        for selector in available_selectors:
            if selector.label != label:
                continue

            # Тестируем селектор
            test_result = self.extract_with_selectors(
                html_or_driver=html, selectors=[selector], use_selenium=False
            )

            extracted_value = test_result.get(label)
            if not extracted_value:
                continue

            # Оцениваем качество извлечения
            score = self._calculate_match_score(
                extracted_value, value, exact, case_sensitive
            )

            if score > best_score:
                best_score = score
                best_selector = selector

        if best_selector:
            self.logger.debug(
                f"Найден лучший селектор для {label} с оценкой {best_score}"
            )
            # Обновляем уверенность селектора
            best_selector.confidence = best_score

        return best_selector

    def _calculate_match_score(
        self, extracted: str, expected: str, exact: bool, case_sensitive: bool
    ) -> float:
        """
        Вычисление оценки соответствия извлеченного значения ожидаемому.

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
            # Точное совпадение
            if extracted_norm == expected_norm:
                return 1.0
            else:
                # Частичное совпадение для точного режима
                if expected_norm in extracted_norm:
                    return 0.7
                else:
                    return 0.0
        else:
            # Частичное совпадение
            if expected_norm in extracted_norm:
                # Чем больше совпадение, тем выше оценка
                match_ratio = (
                    len(expected_norm) / len(extracted_norm) if extracted_norm else 0
                )
                return min(0.9, 0.5 + match_ratio * 0.4)
            else:
                return 0.0

    def auto_generate_missing_selectors(
        self, resource_config: Dict[str, Any], html: str
    ) -> List[SelectorPattern]:
        """
        Автоматическая генерация отсутствующих селекторов для ресурса.

        Args:
            resource_config: Конфигурация ресурса
            html: HTML страницы ресурса

        Returns:
            List[SelectorPattern]: Сгенерированные селекторы
        """
        self.logger.info(
            f"Автогенерация селекторов для ресурса {resource_config.get('id')}"
        )

        # Получаем тестовые данные из конфигурации
        test_data = resource_config.get("test_data")
        if not test_data or not test_data.get("label_value_pairs"):
            self.logger.warning("Нет тестовых данных для автогенерации селекторов")
            return []

        label_value_pairs = test_data["label_value_pairs"]

        # Генерируем селекторы
        generated = self.generate_selectors(
            html=html,
            label_value_pairs=label_value_pairs,
            exact=True,
            case_sensitive=False,
            search_mode="both",
        )

        # Фильтруем уже существующие селекторы
        existing_labels = {s.label for s in resource_config.get("selectors", [])}
        new_selectors = [s for s in generated if s.label not in existing_labels]

        self.logger.info(f"Сгенерировано {len(new_selectors)} новых селекторов")
        return new_selectors
