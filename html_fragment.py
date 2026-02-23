"""
Модуль для извлечения HTML-фрагментов по паре «название поля – значение».
Основная функция – найти на странице текст названия поля и текст значения,
определить их наименьшего общего предка (Lowest Common Ancestor, LCA)
и вернуть внешний HTML этого предка.

Используется для отладки селекторов, автоматического построения селекторов
и возможного интеграции в парсинг данных.
"""

from typing import List, Optional, Union
from bs4 import BeautifulSoup, NavigableString, PageElement, Tag
import requests
import re
from selenium.webdriver.remote.webdriver import WebDriver

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def find_elements_by_text(
    soup: BeautifulSoup,
    text: str,
    exact: bool = True,
    case_sensitive: bool = False,
) -> List[Tag]:
    """
    Находит все элементы (теги), чей полный текст (`.get_text()`) содержит заданный текст.
    """
    if text is None or text == "":
        return []

    def match(s: str) -> bool:
        target = s if case_sensitive else s.lower()
        needle = text if case_sensitive else text.lower()
        if exact:
            # Нормализуем пробелы: удаляем лишние пробелы и приводим к одному пробелу
            normalized_target = re.sub(r"\s+", " ", target.strip())
            normalized_needle = re.sub(r"\s+", " ", needle.strip())
            return normalized_target == normalized_needle
        else:
            return needle in target

    elements = []
    for tag in soup.find_all(True):  # все теги
        full_text = tag.get_text()
        if match(full_text):
            elements.append(tag)
    return elements


def find_text_nodes(
    soup: BeautifulSoup,
    text: str,
    exact: bool = True,
    case_sensitive: bool = False,
) -> List[PageElement]:
    """
    Находит все текстовые узлы (NavigableString), содержащие заданный текст.
    """
    if text is None or text == "":
        return []

    def match(s: str) -> bool:
        if text is None:
            return False
        target = s if case_sensitive else s.lower()
        needle = text if case_sensitive else text.lower()
        if exact:
            # Нормализуем пробелы: удаляем лишние пробелы и приводим к одному пробелу
            normalized_target = re.sub(r"\s+", " ", target.strip())
            normalized_needle = re.sub(r"\s+", " ", needle.strip())
            return normalized_target == normalized_needle
        else:
            return needle in target

    nodes = soup.find_all(string=lambda s: isinstance(s, NavigableString) and match(s))
    return nodes


def lowest_common_ancestor(
    node_a: PageElement,
    node_b: PageElement,
) -> Optional[Tag]:
    """
    Возвращает наименьшего общего предка (LCA) двух узлов дерева BeautifulSoup.
    """

    # Приводим узлы к тегам (для NavigableString берём родителя)
    def to_tag(node: PageElement) -> Optional[Tag]:
        if isinstance(node, Tag):
            return node
        elif isinstance(node, NavigableString):
            return node.parent
        return None

    tag_a = to_tag(node_a)
    tag_b = to_tag(node_b)
    if tag_a is None or tag_b is None:
        return None

    # Собираем цепочки предков от узла к корню
    ancestors_a: List[Tag] = []
    while tag_a is not None:
        ancestors_a.append(tag_a)
        tag_a = (
            tag_a.parent
            if tag_a.parent is not None and tag_a.parent.name != "[document]"
            else None
        )

    ancestors_b: List[Tag] = []
    while tag_b is not None:
        ancestors_b.append(tag_b)
        tag_b = (
            tag_b.parent
            if tag_b.parent is not None and tag_b.parent.name != "[document]"
            else None
        )

    # Ищем последний общий тег с конца (самый глубокий)
    common = None
    for a, b in zip(reversed(ancestors_a), reversed(ancestors_b)):
        if a is b:
            common = a
        else:
            break
    return common


def extract_common_parent_html(
    html: Union[str, BeautifulSoup],
    label_text: str,
    value_text: str,
    exact_label: bool = True,
    exact_value: bool = True,
    case_sensitive: bool = False,
    all_matches: bool = True,
    verbose: bool = False,
    search_mode: str = "text",
) -> List[str]:
    """
    Извлекает HTML-фрагменты общих предков для пар «название поля – значение».
    """
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "lxml")

    if verbose:
        print(f"[DEBUG] Режим поиска: {search_mode}")

    if search_mode == "text":
        label_nodes = find_text_nodes(
            soup, label_text, exact=exact_label, case_sensitive=case_sensitive
        )
        value_nodes = find_text_nodes(
            soup, value_text, exact=exact_value, case_sensitive=case_sensitive
        )
    elif search_mode == "element":
        label_nodes = find_elements_by_text(
            soup, label_text, exact=exact_label, case_sensitive=case_sensitive
        )
        value_nodes = find_elements_by_text(
            soup, value_text, exact=exact_value, case_sensitive=case_sensitive
        )
    else:
        raise ValueError(
            f"Неизвестный search_mode: {search_mode}. Допустимые значения: 'text', 'element'."
        )

    if verbose:
        print(f"[DEBUG] Найдено узлов с label '{label_text}': {len(label_nodes)}")
        print(f"[DEBUG] Найдено узлов с value '{value_text}': {len(value_nodes)}")
        if label_nodes:
            sample = label_nodes[0]
            if isinstance(sample, NavigableString):
                sample = sample.strip()[:100]
            else:
                sample = sample.get_text(strip=True)[:100]
            print(f"[DEBUG] Пример label узла: '{sample}'")
        if value_nodes:
            sample = value_nodes[0]
            if isinstance(sample, NavigableString):
                sample = sample.strip()[:100]
            else:
                sample = sample.get_text(strip=True)[:100]
            print(f"[DEBUG] Пример value узла: '{sample}'")

    # Проверка наличия value_nodes
    if not value_nodes:
        if verbose:
            print("[DEBUG] Не найдены value узлы, возвращаем пустой список.")
        return []
    # Если label_text не пустой, но label_nodes отсутствуют — тоже возвращаем пустой список
    if label_text and not label_nodes:
        if verbose:
            print(
                "[DEBUG] Не найдены label узлы (при непустом label), возвращаем пустой список."
            )
        return []

    # Обработка случая, когда метка отсутствует (пустой label_text)
    if label_text == "":
        # Игнорируем label_nodes, обрабатываем только value_nodes
        unique_ancestors = set()
        fragments = []
        for val in value_nodes:
            # Используем самого узла значения в качестве обоих узлов для LCA
            ancestor = lowest_common_ancestor(val, val)
            if ancestor is None:
                continue
            # Пропустить слишком высокие предки (body, html, document)
            if ancestor.name in ("body", "html", "[document]"):
                if verbose:
                    print(f"[DEBUG] Пропущен предок с тегом {ancestor.name}")
                continue
            ancestor_id = id(ancestor)
            if ancestor_id in unique_ancestors:
                if verbose:
                    print(f"[DEBUG] Пропущен дубликат предка {ancestor.name}")
                continue
            unique_ancestors.add(ancestor_id)
            fragments.append(str(ancestor))
            if verbose:
                print(f"[DEBUG] Добавлен фрагмент с тегом {ancestor.name}")
            if not all_matches:
                return fragments
        if verbose:
            print(f"[DEBUG] Всего найдено уникальных фрагментов: {len(fragments)}")
        return fragments

    # Обычная обработка с парой label-value
    unique_ancestors = set()
    fragments = []
    pair_index = 0

    for lbl in label_nodes:
        for val in value_nodes:
            pair_index += 1
            if verbose:
                lbl_text = (
                    lbl.get_text(strip=True)[:50]
                    if hasattr(lbl, "get_text")
                    else str(lbl)[:50]
                )
                val_text = (
                    val.get_text(strip=True)[:50]
                    if hasattr(val, "get_text")
                    else str(val)[:50]
                )
                print(
                    f"[DEBUG] Пара {pair_index}: label='{lbl_text}', value='{val_text}'"
                )
            ancestor = lowest_common_ancestor(lbl, val)
            if ancestor is None:
                if verbose:
                    print("[DEBUG]   LCA не найден")
                continue
            # Пропустить слишком высокие предки (body, html, document)
            if ancestor.name in ("body", "html", "[document]"):
                if verbose:
                    print(f"[DEBUG] Пропущен предок с тегом {ancestor.name}")
                continue
            # Уникальность по id объекта (так как один тег может встречаться несколько раз)
            ancestor_id = id(ancestor)
            if ancestor_id in unique_ancestors:
                if verbose:
                    print(f"[DEBUG] Пропущен дубликат предка {ancestor.name}")
                continue
            unique_ancestors.add(ancestor_id)
            fragments.append(str(ancestor))
            if verbose:
                print(f"[DEBUG] Добавлен фрагмент с тегом {ancestor.name}")
            if not all_matches:
                # Возвращаем только первый найденный фрагмент
                return fragments

    if verbose:
        print(f"[DEBUG] Всего найдено уникальных фрагментов: {len(fragments)}")
    return fragments


def extract_common_parent_from_url(
    url: str,
    label_text: str,
    value_text: str,
    exact_label: bool = True,
    exact_value: bool = True,
    case_sensitive: bool = False,
    all_matches: bool = True,
    verbose: bool = False,
    search_mode: str = "text",
    driver: Optional[WebDriver] = None,
    use_selenium: bool = False,
    **request_kwargs,
) -> List[str]:
    """
    Загружает страницу по URL и извлекает фрагменты через extract_common_parent_html.

    Возвращает пустой список при ошибках сети или HTTP.
    """
    if use_selenium:
        if driver is None:
            raise ValueError(
                "Для использования Selenium необходимо передать driver "
                "или реализовать его создание в этом модуле."
            )
        html = driver.page_source
    else:
        # Добавляем заголовки по умолчанию, если не переданы свои
        kwargs = dict(request_kwargs)
        if "headers" not in kwargs:
            kwargs["headers"] = DEFAULT_HEADERS
        else:
            # Объединяем переданные заголовки с default, приоритет у переданных
            merged_headers = DEFAULT_HEADERS.copy()
            merged_headers.update(kwargs["headers"])
            kwargs["headers"] = merged_headers
        # Добавляем timeout по умолчанию, если не указан
        if "timeout" not in kwargs:
            kwargs["timeout"] = 10

        try:
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            html = response.text
        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"[ERROR] Ошибка при загрузке URL {url}: {e}")
            return []

    return extract_common_parent_html(
        html,
        label_text,
        value_text,
        exact_label=exact_label,
        exact_value=exact_value,
        case_sensitive=case_sensitive,
        all_matches=all_matches,
        verbose=verbose,
        search_mode=search_mode,
    )


def extract_common_parent_from_driver(
    driver: WebDriver,
    label_text: str,
    value_text: str,
    exact_label: bool = True,
    exact_value: bool = True,
    case_sensitive: bool = False,
    all_matches: bool = True,
    verbose: bool = False,
    search_mode: str = "text",
) -> List[str]:
    """
    Удобная обёртка для извлечения фрагментов из уже загруженной страницы Selenium.
    """
    return extract_common_parent_html(
        driver.page_source,
        label_text,
        value_text,
        exact_label=exact_label,
        exact_value=exact_value,
        case_sensitive=case_sensitive,
        all_matches=all_matches,
        verbose=verbose,
        search_mode=search_mode,
    )


if __name__ == "__main__":
    # Пример использования для отладки
    import sys

    if len(sys.argv) < 4:
        print(
            "Использование: python html_fragment.py <URL> <label_text> <value_text> [--selenium]"
        )
        sys.exit(1)
    url = sys.argv[1]
    label = sys.argv[2]
    value = sys.argv[3]
    use_selenium = "--selenium" in sys.argv
    try:
        if use_selenium:
            from drivers import create_chrome_driver
            from config import ScraperConfig

            config = ScraperConfig(headless=False)
            driver = create_chrome_driver(config)
            driver.get(url)
            fragments = extract_common_parent_from_driver(driver, label, value)
            driver.quit()
        else:
            fragments = extract_common_parent_from_url(url, label, value)
        for i, frag in enumerate(fragments, 1):
            print(f"\n=== Фрагмент {i} ===")
            print(frag)
        if not fragments:
            print("Фрагменты не найдены.")
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
