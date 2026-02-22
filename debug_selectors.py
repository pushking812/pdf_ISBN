#!/usr/bin/env python3
"""
Скрипт для отладки селекторов с помощью модуля html_fragment.

Позволяет быстро получить HTML-фрагменты, содержащие пару «название поля – значение»,
что помогает в ручном подборе CSS-селекторов.

Использование:
    python debug_selectors.py <URL> <label_text> <value_text> [--selenium] [--exact] [--case-sensitive]

Пример:
    python debug_selectors.py https://example.com/book "Год издания" "2020"
"""

import sys
import time
import argparse
import random
from typing import Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from html_fragment import (
    extract_common_parent_from_url,
    extract_common_parent_from_driver,
    find_elements_by_text,
    find_text_nodes,
    lowest_common_ancestor,
)
from bs4 import BeautifulSoup, Tag
from typing import Dict, Any, Union, Iterable, Tuple, List
from resources import get_resource_by_url
from config import ScraperConfig


def parse_arguments(
    url: str,
    label: str,
    value: str,
    selenium: bool,
    exact: bool,
    verbose: bool,
    test: bool,
    search_mode: str,
    case_sensitive: bool = False,
    all_matches: bool = False,
) -> argparse.Namespace:
    """Парсит аргументы командной строки и возвращает объект с ними."""
    parser = argparse.ArgumentParser(
        description="Извлечение HTML-фрагментов по паре «название поля – значение»."
    )
    parser.add_argument(
        "url",
        help="URL страницы",
        nargs="?",
        default=url,
    )
    parser.add_argument(
        "label",
        help="Текст названия поля (например, 'Год издания')",
        nargs="?",
        default=label,
    )
    parser.add_argument(
        "value",
        help="Текст значения поля (например, '2020')",
        nargs="?",
        default=value,
    )
    parser.add_argument(
        "--selenium",
        action="store_true",
        help="Использовать Selenium WebDriver (для динамических страниц)",
        default=selenium,
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="Точное совпадение текстов (по умолчанию – частичное)",
        default=exact,
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Учитывать регистр (по умолчанию – нет)",
        default=case_sensitive,
    )
    parser.add_argument(
        "--all-matches",
        action="store_true",
        help="Показать все найденные фрагменты (по умолчанию – только первый)",
        default=all_matches,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Выводить отладочную информацию",
        default=verbose,
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Использовать тестовый набор данных (жёстко закодированные URL и пары)",
        default=test,
    )
    parser.add_argument(
        "--search-mode",
        choices=["text", "element"],
        default=search_mode,
        help="Режим поиска узлов: text (по текстовым узлам), element (по элементам с полным текстом)",
    )
    return parser.parse_args()


def get_test_data_to_parse() -> dict[str, list[dict[str, str]]]:
    """Возвращает тестовый набор данных (URL -> список пар label-value)."""
    return {
        "https://search.rsl.ru/ru/record/01010115385": [
            {"label": "Автор", "value": "МакГрат, Майк"},
            {
                "label": "Заглавие",
                "value": "Программирование на Python : Python. Программирование для начинающих : первый шаг на пути к успешной карьере : для версий 3.1 - 3.4 : 12+",
            },
            {"label": "Выходные данные", "value": "Москва : Эксмо, 2019"},
            {"label": "Физическое описание", "value": "192 с. : ил.; 26 см"},
        ],
        "https://www.chitai-gorod.ru/product/programmirovanie-na-python-v-primerah-i-zadachah-2832349": [
            {"label": "", "value": "Программирование на Python в примерах и задачах"},
            {"label": "Год издания", "value": "2025"},
            {"label": "", "value": "Алексей Васильев"},
            {"label": "Количество страниц", "value": "616"},
        ],
        "https://book.ru/book/943665": [
            {"label": "", "value": "Математика на Python"},
            {"label": "Год издания:", "value": "2022"},
            {"label": "Авторы:", "value": "Криволапов С.Я., Хрипунова М.Б."},
            {"label": "Объем:", "value": "455 стр."},
        ],
    }


def get_test_data_to_search() -> dict[str, list[dict[str, str]]]:
    """Возвращает тестовый набор данных (URL -> список пар label-value)."""
    return {
        "https://search.rsl.ru/ru/record/01010115385": [
            {"label": "Автор", "value": "МакГрат, Майк"},
            {
                "label": "Заглавие",
                "value": "Программирование на Python : Python. Программирование для начинающих : первый шаг на пути к успешной карьере : для версий 3.1 - 3.4 : 12+",
            },
            {"label": "Выходные данные", "value": "Москва : Эксмо, 2019"},
            {"label": "Физическое описание", "value": "192 с. : ил.; 26 см"},
        ],
        "https://www.chitai-gorod.ru/product/programmirovanie-na-python-v-primerah-i-zadachah-2832349": [
            {"label": "", "value": "Программирование на Python в примерах и задачах"},
            {"label": "Год издания", "value": "2025"},
            {"label": "", "value": "Алексей Васильев"},
            {"label": "Количество страниц", "value": "616"},
        ],
        "https://book.ru/book/943665": [
            {"label": "", "value": "Математика на Python"},
            {"label": "Год издания:", "value": "2022"},
            {"label": "Авторы:", "value": "Криволапов С.Я., Хрипунова М.Б."},
            {"label": "Объем:", "value": "455 стр."},
        ],
        "https://book.ru/book/962004": [
            {"label": "", "value": "Многомерный анализ данных на Python"},
            {"label": "Год издания:", "value": "2026"},
            {"label": "Авторы:", "value": "Паршинцева Л.С., Паршинцев А.А."},
            {"label": "Объем:", "value": "129 стр."},
        ],
        "https://book.ru/book/960946": [
            {
                "label": "",
                "value": "Практикум изучения языка программирования PYTHON. Начальный уровень",
            },
            {"label": "Год издания:", "value": "2026"},
            {"label": "Авторы:", "value": "Щербаков А.Г."},
            {"label": "Объем:", "value": "116 стр."},
        ],
    }


def create_driver(headless: bool = False) -> WebDriver:
    """Создаёт и возвращает экземпляр ChromeDriver."""
    from drivers import create_chrome_driver
    from config import ScraperConfig

    config = ScraperConfig(headless=headless)
    return create_chrome_driver(config)


def wait_for_page_with_protection(
    driver: WebDriver, timeout: int = 10, min_delay: float = 1.0, max_delay: float = 3.0
) -> None:
    """
    Ожидает загрузки страницы с защитой от анти-бот систем.

    Args:
        driver: WebDriver экземпляр
        timeout: Максимальное время ожидания появления body (секунды)
        min_delay: Минимальная случайная задержка после загрузки (секунды)
        max_delay: Максимальная случайная задержка после загрузки (секунды)
    """
    # Ожидание базовой загрузки страницы (появление body)
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except Exception as e:
        print(f"[WARN] Timeout ожидания загрузки страницы: {e}")

    # Случайная задержка для обхода защиты ресурсов
    delay = random.uniform(min_delay, max_delay)
    if delay > 0:
        time.sleep(delay)


def search_web(
    url: str,
    is_driver: bool,
    label: str,
    value: str,
    exact_label: bool,
    exact_value: bool,
    case_sensitive: bool,
    all_matches: bool,
    verbose: bool,
    search_mode: str,
    driver: Optional[WebDriver] = None,
) -> list[str]:
    """
    Выполняет поиск фрагментов с использованием Selenium (если is_driver=True) или requests.
    Если передан driver, он используется для Selenium-поиска (is_driver должно быть True).
    Если driver не передан и is_driver=True, создаётся новый драйвер, который закрывается после поиска.
    """
    func = extract_common_parent_from_url
    driver_or_url = url
    created_driver = None

    if is_driver:
        if driver is not None:
            driver_or_url = driver
        else:
            created_driver = create_driver(headless=False)
            driver_or_url = created_driver
            driver_or_url.get(url)
            wait_for_page_with_protection(driver_or_url)
        func = extract_common_parent_from_driver
    else:
        # Если is_driver=False, игнорируем переданный driver (он не должен быть передан)
        pass

    try:
        return func(
            driver_or_url,
            label,
            value,
            exact_label=exact_label,
            exact_value=exact_value,
            case_sensitive=case_sensitive,
            all_matches=all_matches,
            verbose=verbose,
            search_mode=search_mode,
        )
    finally:
        if created_driver is not None:
            created_driver.quit()


def generate_pattern(
    parse_frags: Iterable[Tuple[str, str, str, List[str], Optional[Dict]]],
    args: argparse.Namespace,
) -> List[Dict[str, Any]]:
    """
    Генерирует универсальный паттерн (CSS-селектор или XPath) для извлечения значения поля
    по фрагменту HTML, содержащему пару «ключевое поле – значение».
    """
    search_mode: str = args.search_mode
    exact_label: bool = args.exact
    exact_value: bool = args.exact
    case_sensitive: bool = args.case_sensitive

    patterns = []

    def build_xpath_text_condition(
        text: str, exact: bool = False, case_sensitive: bool = False
    ) -> str:
        """
        Строит XPath условие для поиска текста с учётом нормализации пробелов и регистра.

        Args:
            text: Искомый текст
            exact: Точное совпадение (True) или частичное (False)
            case_sensitive: Учитывать регистр (True) или нет (False)

        Returns:
            XPath условие для использования в contains() или =
        """
        # Экранируем кавычки в тексте
        escaped_text = text.replace("'", "'").replace('"', '"')

        if exact:
            if case_sensitive:
                # Точное совпадение с учётом регистра, нормализация пробелов
                return f"normalize-space(.) = '{escaped_text}'"
            else:
                # Точное совпадение без учёта регистра
                # Используем translate для приведения к нижнему регистру (английские и русские буквы)
                return f"translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ', 'abcdefghijklmnopqrstuvwxyzабвгдеёжзийклмнопрстуфхцчшщъыьэюя') = translate('{escaped_text}', 'ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ', 'abcdefghijklmnopqrstuvwxyzабвгдеёжзийклмнопрстуфхцчшщъыьэюя')"
        else:
            if case_sensitive:
                # Частичное совпадение с учётом регистра
                return f"contains(., '{escaped_text}')"
            else:
                # Частичное совпадение без учёта регистра
                return f"contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ', 'abcdefghijklmnopqrstuvwxyzабвгдеёжзийклмнопрстуфхцчшщъыьэюя'), translate('{escaped_text}', 'ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ', 'abcdefghijklmnopqrstuvwxyzабвгдеёжзийклмнопрстуфхцчшщъыьэюя'))"

    def get_deepest_node(nodes):
        if not nodes:
            return None

        def depth(node):
            d = 0
            while node is not None:
                node = node.parent
                d += 1
            return d

        return max(nodes, key=depth)

    def collect_unique_classes(element, ancestor):
        """
        Собирает все классы элемента и его родителей (до ancestor, не включая),
        возвращает первый класс, уникальный внутри ancestor.
        Если таких нет, возвращает None.
        """
        if not isinstance(element, Tag):
            element = element.parent if element.parent else element
        classes = []
        current = element
        while current is not None and current != ancestor:
            if isinstance(current, Tag) and current.has_attr("class"):
                cls = current["class"]
                if isinstance(cls, str):
                    cls = cls.split()
                if isinstance(cls, list):
                    classes.extend(cls)
            current = current.parent
        # Убрать дубликаты
        seen = set()
        unique = []
        for cls in classes:
            if cls not in seen:
                seen.add(cls)
                unique.append(cls)
        # Проверить уникальность внутри ancestor
        for cls in unique:
            if len(ancestor.select(f".{cls}")) == 1:
                return cls
        return None

    def are_siblings(node1, node2):
        """
        Проверяет, являются ли два узла соседями (siblings) – имеют общего непосредственного родителя.
        Возвращает True, если parent одинаковый и node1 != node2.
        """
        if node1 is None or node2 is None:
            return False
        parent1 = node1.parent if hasattr(node1, "parent") else None
        parent2 = node2.parent if hasattr(node2, "parent") else None
        return parent1 is not None and parent2 is not None and parent1 == parent2

    for parse_frag in parse_frags:
        print("\n=== Фрагмент для генерации паттерна ===")
        print(parse_frag)
        print("=" * 50)

        # Определяем структуру кортежа (старая vs новая)
        if len(parse_frag) == 5:
            url, label_text, value_text, fragments, resource = parse_frag
        else:
            # старая версия (4 элемента)
            url, label_text, value_text, fragments = parse_frag
            resource = None

        # Проверяем, что есть хотя бы один фрагмент
        if not fragments:
            print(
                f"[WARN] Пропуск фрагмента: label='{label_text}', value='{value_text}' - фрагменты не найдены"
            )
            continue

        soup = BeautifulSoup(fragments[0], "lxml")  # html фрагмент

        # Находим узлы label и value
        if search_mode == "text":
            label_nodes = find_text_nodes(
                soup, label_text, exact=exact_label, case_sensitive=case_sensitive
            )
            value_nodes = find_text_nodes(
                soup, value_text, exact=exact_value, case_sensitive=case_sensitive
            )
        else:
            label_nodes = find_elements_by_text(
                soup, label_text, exact=exact_label, case_sensitive=case_sensitive
            )
            value_nodes = find_elements_by_text(
                soup, value_text, exact=exact_value, case_sensitive=case_sensitive
            )

        # Обработка пустого label
        if label_text == "":
            # label не задан, игнорируем label_nodes
            label_node = None
            if not value_nodes:
                raise ValueError("Не удалось найти value во фрагменте")
            value_node = get_deepest_node(value_nodes)
            # Определяем элемент значения (тег)
            value_element = (
                value_node if isinstance(value_node, Tag) else value_node.parent
            )
            # Используем value_element в качестве ancestor (ближайший тег)
            ancestor = value_element
            # Попробуем подняться к родителю, если текущий ancestor не имеет отличительных признаков
            while ancestor is not None and isinstance(ancestor, Tag):
                has_id = ancestor.has_attr("id")
                has_class = ancestor.has_attr("class")
                if has_id or has_class:
                    break
                parent = ancestor.parent
                if (
                    parent is None
                    or not isinstance(parent, Tag)
                    or parent.name in ("body", "html", "[document]")
                ):
                    break
                ancestor = parent
            # Если ancestor всё ещё слишком высокий, попробуем найти более подходящего предка
            while (
                ancestor is not None
                and isinstance(ancestor, Tag)
                and ancestor.name in ("body", "html", "[document]")
            ):
                if ancestor.parent is not None:
                    ancestor = ancestor.parent
                else:
                    break
        else:
            if not label_nodes or not value_nodes:
                raise ValueError("Не удалось найти label или value во фрагменте")
            label_node = get_deepest_node(label_nodes)
            value_node = get_deepest_node(value_nodes)
            ancestor = lowest_common_ancestor(label_node, value_node)

        # Отладочная информация
        if args.verbose:
            print(
                f"[DEBUG generate_pattern] label_text={label_text!r}, value_text={value_text!r}"
            )
            print(
                f"[DEBUG generate_pattern] value_node type={type(value_node)}, value_node={value_node}"
            )
            print(
                f"[DEBUG generate_pattern] ancestor type={type(ancestor)}, ancestor={ancestor}"
            )
            if hasattr(value_node, "name"):
                print(f"[DEBUG generate_pattern] value_node.name={value_node.name}")
            if isinstance(ancestor, Tag):
                print(f"[DEBUG generate_pattern] ancestor.name={ancestor.name}")

        if ancestor is None:
            raise ValueError("Не удалось найти общего предка для label и value")

        # Определяем атрибут для извлечения
        attribute = "text"
        if isinstance(value_node, Tag):
            if value_node.name == "a":
                # Для пустого label предпочтительнее текст, если он совпадает с искомым значением
                if label_text == "" and value_node.get_text(strip=True) == value_text:
                    attribute = "text"
                else:
                    attribute = "href"
            elif value_node.has_attr("src"):
                attribute = "src"
            elif value_node.has_attr("content"):
                attribute = "content"

        # Пытаемся построить CSS-селектор по уникальному классу или id
        def get_css_selector(element: Tag) -> str:
            # Если есть id – используем его
            if element.has_attr("id"):
                return f"#{element['id']}"
            # Если есть уникальный класс (в пределах фрагмента)
            if element.has_attr("class"):
                classes = element["class"]
                if isinstance(classes, str):
                    classes = classes.split()
                if isinstance(classes, list):
                    for cls in classes:
                        # Проверяем, что этот класс встречается только у данного элемента в soup
                        if len(soup.select(f".{cls}")) == 1:
                            return f".{cls}"
            # Иначе селектор по тегу с учётом родительской структуры (упрощённо)
            # Пока вернём пустую строку, чтобы переключиться на XPath
            return ""

        css_selector = ""
        if isinstance(value_node, Tag):
            css_selector = get_css_selector(value_node)

        if css_selector:
            # Проверим, что селектор уникально выбирает value внутри ancestor
            # (пропустим сложную проверку)
            pattern = {
                "type": "css",
                "selector": css_selector,
                "attribute": attribute,
                "label_text": label_text,
                "value_text": value_text,
                "clean_regex": None,
                "resource_id": resource.get("id") if resource else None,
            }
        else:
            # Генерируем XPath с использованием классов и структуры
            # Определяем элемент значения (тег)
            value_element = (
                value_node if isinstance(value_node, Tag) else value_node.parent
            )
            # Собираем уникальный класс значения (включая родительские классы)
            selected_class = collect_unique_classes(value_element, ancestor)

            # Собираем классы предка
            ancestor_classes = []
            if ancestor.has_attr("class"):
                classes = ancestor["class"]
                if isinstance(classes, str):
                    classes = classes.split()
                if isinstance(classes, list):
                    ancestor_classes = classes

            # Определяем тег значения
            value_tag = value_element.name if isinstance(value_element, Tag) else "*"

            if selected_class:
                # XPath по уникальному классу значения
                xpath = f"//*[contains(@class, '{selected_class}')]"
            else:
                # Пытаемся использовать sibling отношение, если label задан и узлы являются соседями
                if (
                    label_text
                    and label_node is not None
                    and are_siblings(label_node, value_node)
                ):
                    # Определяем тег label
                    label_tag = label_node.name if isinstance(label_node, Tag) else "*"
                    ancestor_class_part = ""
                    if ancestor_classes:
                        ancestor_class_part = (
                            f"[contains(@class, '{ancestor_classes[0]}')]"
                        )
                    # XPath: ancestor с классом, содержащий label с текстом, затем следующий sibling значения
                    label_condition = build_xpath_text_condition(
                        label_text, exact=exact_label, case_sensitive=case_sensitive
                    )
                    xpath = f"//*{ancestor_class_part}[.//{label_tag}[{label_condition}]]//{label_tag}[{label_condition}]/following-sibling::{value_tag}"
                else:
                    # Стандартный fallback с исключением label (если label задан)
                    ancestor_class_part = ""
                    if ancestor_classes:
                        ancestor_class_part = (
                            f"[contains(@class, '{ancestor_classes[0]}')]"
                        )
                    if label_text:
                        # Исключаем элемент, содержащий текст label
                        label_condition = build_xpath_text_condition(
                            label_text, exact=exact_label, case_sensitive=case_sensitive
                        )
                        xpath = f"//*{ancestor_class_part}[.//*[{label_condition}]]//{value_tag}[not({label_condition})]"
                    else:
                        xpath = f"//*{ancestor_class_part}//{value_tag}"

            pattern = {
                "type": "xpath",
                "selector": xpath,
                "attribute": attribute,
                "label_text": label_text,
                "value_text": value_text,
                "clean_regex": None,
                "resource_id": resource.get("id") if resource else None,
            }

        print(
            f"Сгенерирован паттерн: {pattern['type']} -> {pattern['selector']} (атрибут: {pattern['attribute']})"
        )

        patterns.append(pattern)

    return patterns


def extract_value(
    html_or_driver: Union[str, WebDriver],
    pattern: Dict[str, Any],
    use_selenium: Optional[bool] = None,
) -> Optional[str]:
    """
    Извлекает значение поля из HTML или страницы Selenium по заданному паттерну.
    """
    from selenium.webdriver.common.by import By

    # Определяем, работаем ли с Selenium
    is_selenium = (
        use_selenium
        if use_selenium is not None
        else isinstance(html_or_driver, WebDriver)
    )

    if is_selenium:
        driver = html_or_driver
        selector = pattern["selector"]
        selector_type = pattern["type"]

        try:
            if selector_type == "css":
                element = driver.find_element(By.CSS_SELECTOR, selector)
            elif selector_type == "xpath":
                element = driver.find_element(By.XPATH, selector)
            else:
                raise ValueError(f"Неизвестный тип селектора: {selector_type}")
        except Exception:
            # Элемент не найден
            return None
    else:
        html = html_or_driver
        soup = BeautifulSoup(html, "lxml")
        selector = pattern["selector"]
        selector_type = pattern["type"]

        if selector_type == "css":
            element = soup.select_one(selector)
            if element is None:
                return None
        elif selector_type == "xpath":
            # Используем lxml для XPath
            from lxml import etree

            tree = etree.HTML(html)
            try:
                elements = tree.xpath(selector)
                if not elements:
                    return None
                element = elements[0]
                # Элемент lxml.etree._Element, извлекаем значение в зависимости от атрибута
                # Обработка будет выполнена ниже в общем блоке кода
                pass  # Продолжаем выполнение, element уже содержит lxml элемент
            except Exception:
                return None
        else:
            raise ValueError(f"Неизвестный тип селектора: {selector_type}")

    # Извлекаем значение в зависимости от атрибута
    attribute = pattern.get("attribute", "text")

    if is_selenium:
        if attribute == "text":
            value = element.text
        else:
            value = element.get_attribute(attribute)
    else:
        # BeautifulSoup или lxml элемент
        if selector_type == "css":
            if attribute == "text":
                value = element.get_text(strip=True)
            else:
                value = element.get(attribute)
        else:  # xpath с lxml
            if attribute == "text":
                # Используем XPath string() для извлечения всего текста элемента и его потомков
                text = element.xpath("string()")
                value = text if isinstance(text, str) else (text[0] if text else "")
            else:
                value = element.get(attribute)

    if value is None:
        return None

    # Применяем clean_regex, если есть
    clean_regex = pattern.get("clean_regex")
    if clean_regex and value:
        import re

        match = re.search(clean_regex, value)
        if match:
            value = match.group(1) if match.groups() else match.group(0)

    return value.strip() if isinstance(value, str) else str(value)


def print_fragments(fragments: list[tuple]) -> None:
    """Выводит найденные фрагменты в консоль."""
    if not fragments:
        print("❌ Фрагменты не найдены.")
        return
    print(f"Найдено фрагментов: {len(fragments)}")
    for i, frag in enumerate(fragments, 1):
        print(f"\n=== Фрагмент {i} ===")
        print(f"URL: {frag[0]}, Label: '{frag[1]}', Value: '{frag[2]}'")
        print("-" * 50)
        print(frag[3])
        print("=" * 50)


def run_parse(args: argparse.Namespace, driver=None) -> Union[bool, list[str]]:
    """
    Выполняет поиск фрагментов на основе аргументов.
    Возвращает True, если хотя бы один фрагмент найден, иначе False.
    """
    # Определяем данные для поиска
    if args.test:
        search_data = get_test_data_to_parse()
    else:
        search_data = {args.url: [{"label": args.label, "value": args.value}]}

    all_fragments = []
    driver_created = False
    if driver is None and args.selenium:
        driver = create_driver(headless=False)
        driver_created = True
    try:
        for url, pairs in search_data.items():
            if args.verbose:
                print(f"\n🔍 Проверка URL: {url}")

            if driver:
                driver.get(url)
                wait_for_page_with_protection(driver)

            for pair in pairs:
                if args.verbose:
                    print(
                        f"\n=== Поиск пары: '{pair['label']}' – '{pair['value']}' ==="
                    )

                fragments = search_web(
                    url,
                    is_driver=args.selenium,
                    label=pair["label"],
                    value=pair["value"],
                    exact_label=args.exact,
                    exact_value=args.exact,
                    case_sensitive=args.case_sensitive,
                    all_matches=args.all_matches,
                    verbose=args.verbose,
                    search_mode=args.search_mode,
                    driver=driver,
                )
                config = ScraperConfig()
                resource = get_resource_by_url(url, config)
                if fragments:
                    all_fragments.extend(
                        [(url, pair["label"], pair["value"], fragments, resource)]
                    )
                else:
                    if args.verbose:
                        print(
                            f"[WARN] Для пары '{pair['label']}' - '{pair['value']}' фрагменты не найдены"
                        )
    finally:
        if driver_created and driver:
            driver.quit()

    if not all_fragments:
        print("❌ Фрагменты не найдены.")
        if not args.verbose:
            print(
                "💡 Попробуйте запустить с параметром --verbose, чтобы увидеть отладочную информацию."
            )
        return False

    print_fragments(all_fragments)  # html фрагменты для первой пары (для наглядности)
    return all_fragments


def run_search(args, patterns, driver=None) -> list[Optional[str]]:
    search_data = get_test_data_to_search()
    all_extracted = []

    # Создаём драйвер один раз, если используется Selenium
    driver_created = False
    if driver is None and args.selenium:
        driver = create_driver(headless=False)
        driver_created = True

    # Группируем паттерны по resource_id для быстрого поиска
    patterns_by_resource = {}
    patterns_without_resource = []
    # Дополнительно создаём маппинг по ключам (resource_id, label, value) для точного соответствия
    patterns_by_key = {}

    for pat in patterns:
        resource_id = pat.get("resource_id")
        label_text = pat.get("label_text", "")
        value_text = pat.get("value_text", "")

        if resource_id:
            patterns_by_resource.setdefault(resource_id, []).append(pat)
            # Создаём ключ для точного соответствия
            key = (resource_id, label_text, value_text)
            patterns_by_key[key] = pat
        else:
            patterns_without_resource.append(pat)
            # Для паттернов без resource_id используем только label/value
            key = (None, label_text, value_text)
            patterns_by_key[key] = pat

    def find_best_pattern(resource_id, label, value, available_patterns):
        """
        Находит наилучший паттерн для заданной пары (label, value) и resource_id.

        Приоритет поиска:
        1. Точное совпадение по (resource_id, label, value)
        2. Совпадение по (resource_id, label) (value может отличаться)
        3. Совпадение по (resource_id) (только resource_id)
        4. Любой паттерн без resource_id с совпадением label/value
        5. Первый доступный паттерн
        """
        # 1. Точное совпадение
        exact_key = (resource_id, label, value)
        if exact_key in patterns_by_key:
            return patterns_by_key[exact_key]

        # 2. Совпадение по resource_id и label (value любое)
        if resource_id:
            for key, pat in patterns_by_key.items():
                if key[0] == resource_id and key[1] == label:
                    return pat

        # 3. Совпадение только по resource_id
        if resource_id and resource_id in patterns_by_resource:
            # Возвращаем первый паттерн для этого ресурса
            return patterns_by_resource[resource_id][0]

        # 4. Паттерны без resource_id с совпадением label/value
        for pat in patterns_without_resource:
            if pat.get("label_text") == label and pat.get("value_text") == value:
                return pat

        # 5. Первый доступный паттерн
        if available_patterns:
            return available_patterns[0]

        return None

    # Конфиг для определения ресурса по URL
    config = ScraperConfig()

    try:
        for url, pairs in search_data.items():
            # Определяем ресурс по URL
            resource = get_resource_by_url(url, config)
            resource_id = resource.get("id") if resource else None

            # Получаем список паттернов для данного ресурса
            resource_patterns = []
            if resource_id and resource_id in patterns_by_resource:
                resource_patterns = patterns_by_resource[resource_id]
            elif patterns_without_resource:
                resource_patterns = patterns_without_resource
            elif patterns:
                resource_patterns = patterns
            else:
                print("[ERROR] Нет доступных паттернов")

            print(f"\n🔍 Проверка URL: {url} (ресурс: {resource_id})")
            print(f"   Доступно паттернов для ресурса: {len(resource_patterns)}")

            if driver:
                driver.get(url)
                wait_for_page_with_protection(driver)

            for idx, pair in enumerate(pairs):
                print(f"\n=== Поиск пары: '{pair['label']}' – '{pair['value']}' ===")

                # Выбираем наилучший паттерн для текущей пары
                pattern = find_best_pattern(
                    resource_id, pair["label"], pair["value"], resource_patterns
                )

                if pattern:
                    print(
                        f"[DEBUG] Используется паттерн: {pattern['type']} -> {pattern['selector']}"
                    )
                    print(
                        f"[DEBUG] Паттерн соответствует: label='{pattern.get('label_text')}', value='{pattern.get('value_text')}'"
                    )
                else:
                    print("[WARN] Не удалось выбрать паттерн для извлечения")

                search_frags = search_web(
                    url=url,
                    is_driver=args.selenium,
                    label=pair["label"],
                    value=pair["value"],
                    exact_label=args.exact,
                    exact_value=args.exact,
                    case_sensitive=args.case_sensitive,
                    all_matches=args.all_matches,
                    verbose=args.verbose,
                    search_mode=args.search_mode,
                    driver=driver,
                )

                if not search_frags:
                    print("[WARN] Фрагменты не найдены, пропускаем")
                    # Пытаемся извлечь значение напрямую по паттерну, если он есть
                    if pattern:
                        if driver is not None:
                            extracted = extract_value(driver, pattern)
                        else:
                            # Загружаем HTML через requests
                            import requests
                            from requests.exceptions import RequestException

                            try:
                                resp = requests.get(
                                    url,
                                    headers={"User-Agent": "Mozilla/5.0"},
                                    timeout=10,
                                )
                                resp.raise_for_status()
                                extracted = extract_value(resp.text, pattern)
                            except RequestException as e:
                                print(f"[ERROR] Не удалось загрузить страницу: {e}")
                                extracted = None
                    else:
                        extracted = None
                elif pattern:
                    extracted = extract_value(search_frags[0], pattern)
                else:
                    extracted = None
                    print("[ERROR] Не удалось выбрать паттерн для извлечения")

                print(f"Извлечённое значение: {extracted}")

                all_extracted.append(extracted)
    finally:
        if driver_created and driver is not None:
            driver.quit()

    return all_extracted


def main() -> None:
    default_arg_values = {
        "url": r"https://book.ru/book/943665",
        "label": "Год издания:",
        "value": "2022",
        "selenium": False,
        "exact": True,
        "verbose": False,
        "test": True,
        "search_mode": "element",
        "all_matches": True,
    }
    args = parse_arguments(**default_arg_values)

    driver = None
    if args.selenium:
        driver = create_driver(headless=False)

    try:
        parse_frags = run_parse(args, driver=driver)
        if not parse_frags:
            print("   ❌ Фрагменты не найдены.")
            sys.exit(1)

        patterns = generate_pattern(parse_frags, args=args)

        run_search(args, patterns, driver=driver)
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    main()
