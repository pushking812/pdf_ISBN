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
from typing import Optional
from selenium.webdriver.remote.webdriver import WebDriver

from html_fragment import (
    extract_common_parent_from_url,
    extract_common_parent_from_driver,
    find_elements_by_text,
    find_text_nodes,
    lowest_common_ancestor,
)
from bs4 import BeautifulSoup, Tag
from typing import Dict, Any, Union


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
        nargs='?',
        default=url,
        )
    parser.add_argument(
        "label",
        help="Текст названия поля (например, 'Год издания')",
        nargs='?',
        default = label,
        )
    parser.add_argument(
        "value",
        help="Текст значения поля (например, '2020')",
        nargs='?',
        default = value,
        )
    parser.add_argument(
        "--selenium",
        action="store_true",
        help="Использовать Selenium WebDriver (для динамических страниц)",
        default = selenium,
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
        default = case_sensitive,
    )
    parser.add_argument(
        "--all-matches",
        action="store_true",
        help="Показать все найденные фрагменты (по умолчанию – только первый)",
        default = all_matches,
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


def get_test_data_to_parse() -> dict[str, list[tuple[str, str]]]:
    """Возвращает тестовый набор данных (URL -> список пар label-value)."""
    return {
        "https://www.chitai-gorod.ru/product/programmirovanie-na-python-v-primerah-i-zadachah-2832349": [
            {'label':'', 'value': 'Программирование на Python в примерах и задачах'},
            {'label':'Год издания', 'value': '2025'},
            {'label':'', 'value': 'Алексей Васильев'}, 
            {'label':'Количество страниц', 'value': '616'},
        ],
        # "https://book.ru/book/943665": [
        #     {'label':'', 'value': 'Математика на Python'},
        #     {'label':'Год издания:', 'value': '2022'},
        #     {'label':'Авторы:', 'value': 'Криволапов С.Я., Хрипунова М.Б.'},
        #     {'label':'Объем:', 'value': '455 стр.'}
        # ],
    }
    
def get_test_data_to_search() -> dict[str, list[tuple[str, str]]]:
    """Возвращает тестовый набор данных (URL -> список пар label-value)."""
    return {
        "https://www.chitai-gorod.ru/product/programmirovanie-na-python-v-primerah-i-zadachah-2832349": [
            {'label':'', 'value': 'Программирование на Python в примерах и задачах'},
            {'label':'Год издания', 'value': '2025'},
            {'label':'', 'value': 'Алексей Васильев'}, 
            {'label':'Количество страниц', 'value': '616'},
        ],
        # "https://book.ru/book/943665": [
        #     {'label':'', 'value': 'Математика на Python'},
        #     {'label':'Год издания:', 'value': '2022'},
        #     {'label':'Авторы:', 'value': 'Криволапов С.Я., Хрипунова М.Б.'},
        #     {'label':'Объем:', 'value': '455 стр.'}
        # ],
        # "https://book.ru/book/962004": [
        #      {'label':'', 'value': 'Многомерный анализ данных на Python'},
        #      {'label':'Год издания:', 'value': '2026'},
        #      {'label':'Авторы:', 'value': 'Паршинцева Л.С., Паршинцев А.А.'},
        #      {'label':'Объем:', 'value': '129 стр.'}
        # ],
        # "https://book.ru/book/960946": [
        #     {'label':'', 'value': 'Практикум изучения языка программирования PYTHON. Начальный уровень'},
        #     {'label':'Год издания:', 'value': '2026'},
        #     {'label':'Авторы:', 'value': 'Щербаков А.Г.'},
        #     {'label':'Объем:', 'value': '116 стр.'}
        # ],
    }


def create_driver(headless: bool = False) -> WebDriver:
    """Создаёт и возвращает экземпляр ChromeDriver."""
    from drivers import create_chrome_driver
    from config import ScraperConfig
    config = ScraperConfig(headless=headless)
    return create_chrome_driver(config)


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
            time.sleep(5)
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
    parse_frags: str,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """
    Генерирует универсальный паттерн (CSS-селектор или XPath) для извлечения значения поля
    по фрагменту HTML, содержащему пару «ключевое поле – значение».
    """
    search_mode: str = args.search_mode
    exact_label: bool = args.exact
    exact_value: bool = args.exact
    case_sensitive: bool = args.case_sensitive
    
    patterns = []
    
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
    
    for parse_frag in parse_frags:
        print("\n=== Фрагмент для генерации паттерна ===")
        print(parse_frag)
        print("=" * 50)
    
        label_text: str= parse_frag[1] # label
        value_text: str= parse_frag[2] # value
    
        soup = BeautifulSoup(parse_frag[-1][0], "lxml") # html фрагмент
    
        # Находим узлы label и value
        if search_mode == "text":
            label_nodes = find_text_nodes(soup, label_text, exact=exact_label, case_sensitive=case_sensitive)
            value_nodes = find_text_nodes(soup, value_text, exact=exact_value, case_sensitive=case_sensitive)
        else:
            label_nodes = find_elements_by_text(soup, label_text, exact=exact_label, case_sensitive=case_sensitive)
            value_nodes = find_elements_by_text(soup, value_text, exact=exact_value, case_sensitive=case_sensitive)
    
        # Обработка пустого label
        if label_text == "":
            # label не задан, игнорируем label_nodes
            label_node = None
            if not value_nodes:
                raise ValueError("Не удалось найти value во фрагменте")
            value_node = get_deepest_node(value_nodes)
            # Определяем элемент значения (тег)
            value_element = value_node if isinstance(value_node, Tag) else value_node.parent
            # Используем value_element в качестве ancestor (ближайший тег)
            ancestor = value_element
            # Попробуем подняться к родителю, если текущий ancestor не имеет отличительных признаков
            while ancestor is not None and isinstance(ancestor, Tag):
                has_id = ancestor.has_attr('id')
                has_class = ancestor.has_attr('class')
                if has_id or has_class:
                    break
                parent = ancestor.parent
                if parent is None or not isinstance(parent, Tag) or parent.name in ('body', 'html', '[document]'):
                    break
                ancestor = parent
            # Если ancestor всё ещё слишком высокий, попробуем найти более подходящего предка
            while ancestor is not None and isinstance(ancestor, Tag) and ancestor.name in ('body', 'html', '[document]'):
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
            print(f"[DEBUG generate_pattern] label_text={label_text!r}, value_text={value_text!r}")
            print(f"[DEBUG generate_pattern] value_node type={type(value_node)}, value_node={value_node}")
            print(f"[DEBUG generate_pattern] ancestor type={type(ancestor)}, ancestor={ancestor}")
            if hasattr(value_node, 'name'):
                print(f"[DEBUG generate_pattern] value_node.name={value_node.name}")
            if isinstance(ancestor, Tag):
                print(f"[DEBUG generate_pattern] ancestor.name={ancestor.name}")
        
        if ancestor is None:
            raise ValueError("Не удалось найти общего предка для label и value")
    
        # Определяем атрибут для извлечения
        attribute = "text"
        if isinstance(value_node, Tag):
            if value_node.name == "a":
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
            }
        else:
            # Генерируем XPath с использованием классов и структуры
            # Определяем элемент значения (тег)
            value_element = value_node if isinstance(value_node, Tag) else value_node.parent
            # Собираем классы элемента значения
            value_classes = []
            if isinstance(value_element, Tag) and value_element.has_attr("class"):
                classes = value_element["class"]
                if isinstance(classes, str):
                    classes = classes.split()
                if isinstance(classes, list):
                    value_classes = classes
            # Собираем классы предка
            ancestor_classes = []
            if ancestor.has_attr("class"):
                classes = ancestor["class"]
                if isinstance(classes, str):
                    classes = classes.split()
                if isinstance(classes, list):
                    ancestor_classes = classes
            
            # Пытаемся построить точный XPath
            # Вариант 1: если у значения есть уникальный класс в пределах предка
            selected_class = None
            for cls in value_classes:
                # Проверяем, что этот класс встречается только один раз внутри ancestor
                if len(ancestor.select(f".{cls}")) == 1:
                    selected_class = cls
                    break
            
            if selected_class:
                # XPath по классу значения с привязкой к label
                xpath = f"//*[contains(@class, '{selected_class}')]"
            else:
                # Используем структуру: ancestor с классом + label текст + значение по тегу
                ancestor_class_part = ""
                if ancestor_classes:
                    ancestor_class_part = f"[contains(@class, '{ancestor_classes[0]}')]"
                value_tag = value_element.name if isinstance(value_element, Tag) else "*"
                if label_text:
                    xpath = f"//*{ancestor_class_part}[.//*[contains(text(), '{label_text}')]]//{value_tag}"
                else:
                    xpath = f"//*{ancestor_class_part}//{value_tag}"
            
            pattern = {
                "type": "xpath",
                "selector": xpath,
                "attribute": attribute,
                "label_text": label_text,
                "value_text": value_text,
                "clean_regex": None,
            }
            
        print(f"Сгенерирован паттерн: {pattern['type']} -> {pattern['selector']} (атрибут: {pattern['attribute']})")
        
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
    is_selenium = use_selenium if use_selenium is not None else isinstance(html_or_driver, WebDriver)
    
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
                # Преобразуем элемент lxml в строку для извлечения атрибутов/текста
                # Для простоты будем работать с lxml.etree._Element
                pass
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
                value = element.text
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
        search_data = {
            args.url: [(args.label, args.value)]
        }

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
                time.sleep(5)

            
            for pair in pairs:
                if args.verbose:
                    print(f"\n=== Поиск пары: '{pair['label']}' – '{pair['value']}' ===")

                fragments = search_web(
                    url,
                    is_driver=args.selenium,
                    label=pair['label'],
                    value=pair['value'],
                    exact_label=args.exact,
                    exact_value=args.exact,
                    case_sensitive=args.case_sensitive,
                    all_matches=args.all_matches,
                    verbose=args.verbose,
                    search_mode=args.search_mode,
                    driver=driver,
                )
                all_fragments.extend([(url, pair['label'], pair['value'], fragments)])
    finally:
        if driver_created and driver:
            driver.quit()

    if not all_fragments:
        print("❌ Фрагменты не найдены.")
        if not args.verbose:
            print("💡 Попробуйте запустить с параметром --verbose, чтобы увидеть отладочную информацию.")
        return False

    print_fragments(all_fragments) # html фрагменты для первой пары (для наглядности)
    return all_fragments


def run_search(args, patterns, driver=None) -> list[Optional[str]]:
    search_data = get_test_data_to_search()
    all_extracted = []
    
    # Создаём драйвер один раз, если используется Selenium
    driver_created = False
    if driver is None and args.selenium:
        driver = create_driver(headless=False)
        driver_created = True
    
    try:
        for url, pairs in search_data.items():
            print(f"\n🔍 Проверка URL: {url} с паттерном '{patterns[0]['type']}'")
            
            if driver:
                driver.get(url)
                time.sleep(5)
            
            for idx, pair in enumerate(pairs):
                # Выбираем соответствующий паттерн, если есть, иначе первый
                pattern = patterns[idx] if idx < len(patterns) else patterns[0]
                print(f"\n=== Поиск пары: '{pair['label']}' – '{pair['value']}' ===")
                print(f"[DEBUG] Используется паттерн: {pattern['type']} -> {pattern['selector']}")
                
                search_frags = search_web(
                    url=url,
                    is_driver=args.selenium,
                    label=pair['label'],
                    value=pair['value'],
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
                    extracted = None
                else:
                    extracted = extract_value(search_frags[0], pattern)
                
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
        "selenium": True,
        "exact": True,
        "verbose": True,
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
            
        patterns = generate_pattern(
            parse_frags,
            args = args
        )
        
        run_search(args, patterns, driver=driver)
    finally:
        if driver is not None:
            driver.quit()

if __name__ == "__main__":
    main()
