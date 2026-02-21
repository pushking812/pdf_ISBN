"""
Модуль для извлечения HTML-фрагментов по паре «название поля – значение».
Основная функция – найти на странице текст названия поля и текст значения,
определить их наименьшего общего предка (Lowest Common Ancestor, LCA)
и вернуть внешний HTML этого предка.

Используется для отладки селекторов, автоматического построения селекторов
и возможного интеграции в парсинг данных.
"""

from typing import List, Optional, Union, Tuple
from bs4 import BeautifulSoup, NavigableString, PageElement, Tag, Comment
import requests
from selenium.webdriver.remote.webdriver import WebDriver


def clean_html_structure(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Удаляет комментарии и объединяет смежные текстовые узлы внутри каждого тега.
    Модифицирует переданный объект soup (in‑place) и возвращает его.
    """
    # Удаляем все комментарии
    for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Объединяем смежные текстовые узлы
    for tag in soup.find_all(True):  # все теги
        new_children = []
        current_text = []
        for child in tag.contents:
            if isinstance(child, NavigableString):
                current_text.append(child)
            else:
                if current_text:
                    new_children.append(NavigableString("".join(current_text)))
                    current_text = []
                new_children.append(child)
        if current_text:
            new_children.append(NavigableString("".join(current_text)))
        tag.contents = new_children

    return soup


def find_elements_by_text(
    soup: BeautifulSoup,
    text: str,
    exact: bool = True,
    case_sensitive: bool = False,
) -> List[Tag]:
    """
    Находит все элементы (теги), чей полный текст (`.get_text()`) содержит заданный текст.

    Параметры:
        soup: объект BeautifulSoup.
        text: искомый текст.
        exact: если True, ищет точное совпадение (после strip),
               если False – частичное вхождение.
        case_sensitive: учитывать регистр (по умолчанию False).

    Возвращает:
        Список найденных тегов.
    """
    def match(s: str) -> bool:
        target = s if case_sensitive else s.lower()
        needle = text if case_sensitive else text.lower()
        if exact:
            return target.strip() == needle
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

    Параметры:
        soup: объект BeautifulSoup.
        text: искомый текст.
        exact: если True, ищет точное совпадение (после strip),
               если False – частичное вхождение.
        case_sensitive: учитывать регистр (по умолчанию False).

    Возвращает:
        Список найденных узлов (NavigableString).
    """
    def match(s: str) -> bool:
        target = s if case_sensitive else s.lower()
        needle = text if case_sensitive else text.lower()
        if exact:
            return target.strip() == needle
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

    Если один из узлов – текстовый (NavigableString), берётся его родительский тег.
    Если узлы не имеют общего предка (разные документы), возвращается None.

    Параметры:
        node_a, node_b: узлы (Tag или NavigableString).

    Возвращает:
        Тег – общего предка или None.
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
        tag_a = tag_a.parent if tag_a.parent is not None and tag_a.parent.name != "[document]" else None

    ancestors_b: List[Tag] = []
    while tag_b is not None:
        ancestors_b.append(tag_b)
        tag_b = tag_b.parent if tag_b.parent is not None and tag_b.parent.name != "[document]" else None

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

    Алгоритм:
        1. В зависимости от search_mode находит узлы или элементы,
           содержащие label_text и value_text.
        2. Для каждой пары (label_node, value_node) вычисляет LCA.
        3. Собирает уникальные LCA (по id тега) и возвращает их внешний HTML.

    Параметры:
        html: HTML-строка или уже разобранный объект BeautifulSoup.
        label_text: текст названия поля (например, "Год издания").
        value_text: текст значения поля (например, "2020").
        exact_label: точное совпадение для label_text.
        exact_value: точное совпадение для value_text.
        case_sensitive: учитывать регистр при поиске текста.
        all_matches: если True – вернуть все найденные фрагменты,
                     если False – только первый (или пустой список).
        verbose: если True – выводить отладочную информацию.
        search_mode: режим поиска узлов:
            - "text": поиск по текстовым узлам (NavigableString).
            - "element": поиск по элементам (тегам) с полным текстом.
            - "cleaned": предварительная очистка комментариев и объединение
              смежных текстовых узлов, затем поиск как в "text".

    Возвращает:
        Список строк – outer HTML каждого общего предка.
        Если пары не найдены – пустой список.
    """
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "lxml")

    if verbose:
        print(f"[DEBUG] Режим поиска: {search_mode}")

    # Обработка режима cleaned
    if search_mode == "cleaned":
        # Создаём копию, чтобы не модифицировать исходный soup
        soup = BeautifulSoup(str(soup), "lxml")
        clean_html_structure(soup)
        search_mode = "text"  # после очистки используем обычный поиск по текстовым узлам

    if search_mode == "text":
        label_nodes = find_text_nodes(soup, label_text, exact=exact_label, case_sensitive=case_sensitive)
        value_nodes = find_text_nodes(soup, value_text, exact=exact_value, case_sensitive=case_sensitive)
    elif search_mode == "element":
        label_nodes = find_elements_by_text(soup, label_text, exact=exact_label, case_sensitive=case_sensitive)
        value_nodes = find_elements_by_text(soup, value_text, exact=exact_value, case_sensitive=case_sensitive)
    else:
        raise ValueError(f"Неизвестный search_mode: {search_mode}. Допустимые значения: 'text', 'element', 'cleaned'.")

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

    if not label_nodes or not value_nodes:
        if verbose:
            print("[DEBUG] Не найдены label или value узлы, возвращаем пустой список.")
        return []

    unique_ancestors = set()
    fragments = []

    for lbl in label_nodes:
        for val in value_nodes:
            ancestor = lowest_common_ancestor(lbl, val)
            if ancestor is None:
                continue
            # Пропустить слишком высокие предки (body, html, document)
            if ancestor.name in ('body', 'html', '[document]'):
                if verbose:
                    print(f"[DEBUG] Пропущен предок с тегом {ancestor.name}")
                continue
            # Уникальность по id объекта (так как один тег может встречаться несколько раз)
            ancestor_id = id(ancestor)
            if ancestor_id in unique_ancestors:
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
    use_selenium: bool = False,
    driver: Optional[WebDriver] = None,
    **request_kwargs,
) -> List[str]:
    """
    Загружает страницу по URL и извлекает фрагменты через extract_common_parent_html.

    Параметры:
        url: адрес страницы.
        label_text, value_text: см. extract_common_parent_html.
        exact_label, exact_value, case_sensitive, all_matches, verbose, search_mode:
            параметры, передаваемые в extract_common_parent_html.
        search_mode: режим поиска узлов (см. extract_common_parent_html).
        use_selenium: если True – использовать Selenium WebDriver,
                      если False – простой requests (статический контент).
        driver: опционально переданный драйвер Selenium (если use_selenium=True).
        **request_kwargs: дополнительные аргументы для requests.get().

    Возвращает:
        Список фрагментов (аналогично extract_common_parent_html).

    Примечание:
        Если use_selenium=True, но driver не передан, будет создан новый драйвер
        (требуется установленный ChromeDriver). В настоящей реализации создание
        драйвера не реализовано – нужно передать готовый.
    """
    if use_selenium:
        if driver is None:
            raise ValueError(
                "Для использования Selenium необходимо передать driver "
                "или реализовать его создание в этом модуле."
            )
        html = driver.page_source
    else:
        response = requests.get(url, **request_kwargs)
        response.raise_for_status()
        html = response.text

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

    Параметры:
        driver: экземпляр Selenium WebDriver.
        label_text, value_text: см. extract_common_parent_html.
        exact_label, exact_value, case_sensitive, all_matches, verbose, search_mode:
            параметры, передаваемые в extract_common_parent_html.
        search_mode: режим поиска узлов (см. extract_common_parent_html).

    Возвращает:
        Список фрагментов.
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