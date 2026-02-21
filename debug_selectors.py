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
import argparse
from selenium.webdriver.remote.webdriver import WebDriver

from html_fragment import (
    extract_common_parent_from_url,
    extract_common_parent_from_driver,
)


def parse_arguments() -> argparse.Namespace:
    """Парсит аргументы командной строки и возвращает объект с ними."""
    parser = argparse.ArgumentParser(
        description="Извлечение HTML-фрагментов по паре «название поля – значение»."
    )
    parser.add_argument(
        "url",
        help="URL страницы",
        nargs='?',
        default=r"https://book.ru/book/943665",
        )
    parser.add_argument(
        "label",
        help="Текст названия поля (например, 'Год издания')",
        nargs='?',
        default = "Год издания:",
        )
    parser.add_argument(
        "value",
        help="Текст значения поля (например, '2020')",
        nargs='?',
        default = "2022",
        )
    parser.add_argument(
        "--selenium",
        action="store_true",
        help="Использовать Selenium WebDriver (для динамических страниц)",
        default = False,
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="Точное совпадение текстов (по умолчанию – частичное)",
        default=True,
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Учитывать регистр (по умолчанию – нет)",
        default = False,
    )
    parser.add_argument(
        "--all-matches",
        action="store_true",
        help="Показать все найденные фрагменты (по умолчанию – только первый)",
        default = False,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Выводить отладочную информацию",
        default=True,
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Использовать тестовый набор данных (жёстко закодированные URL и пары)",
        default=True,
    )
    parser.add_argument(
        "--search-mode",
        choices=["text", "element"],
        default="element",
        help="Режим поиска узлов: text (по текстовым узлам), element (по элементам с полным текстом)",
    )
    return parser.parse_args()


def get_test_data() -> dict[str, list[tuple[str, str]]]:
    """Возвращает тестовый набор данных (URL -> список пар label-value)."""
    return {
        "https://book.ru/book/943665": [
            ("Год издания:", "2022"),
            ("Авторы:", "Криволапов С.Я., Хрипунова М.Б."),
            ("Объем:", "455 стр."),
        ],
    }


def create_driver(headless: bool = False) -> WebDriver:
    """Создаёт и возвращает экземпляр ChromeDriver."""
    from drivers import create_chrome_driver
    from config import ScraperConfig
    config = ScraperConfig(headless=headless)
    return create_chrome_driver(config)


def search_with_selenium(
    driver: WebDriver,
    url: str,
    label: str,
    value: str,
    exact_label: bool,
    exact_value: bool,
    case_sensitive: bool,
    all_matches: bool,
    verbose: bool,
    search_mode: str,
) -> list[str]:
    """Выполняет поиск фрагментов с использованием Selenium."""
    return extract_common_parent_from_driver(
        driver,
        label,
        value,
        exact_label=exact_label,
        exact_value=exact_value,
        case_sensitive=case_sensitive,
        all_matches=all_matches,
        verbose=verbose,
        search_mode=search_mode,
    )


def search_with_requests(
    url: str,
    label: str,
    value: str,
    exact_label: bool,
    exact_value: bool,
    case_sensitive: bool,
    all_matches: bool,
    verbose: bool,
    search_mode: str,
) -> list[str]:
    """Выполняет поиск фрагментов с использованием requests + BeautifulSoup."""
    return extract_common_parent_from_url(
        url,
        label,
        value,
        exact_label=exact_label,
        exact_value=exact_value,
        case_sensitive=case_sensitive,
        all_matches=all_matches,
        verbose=verbose,
        search_mode=search_mode,
    )


def print_fragments(fragments: list[str]) -> None:
    """Выводит найденные фрагменты в консоль."""
    if not fragments:
        print("❌ Фрагменты не найдены.")
        return
    print(f"Найдено фрагментов: {len(fragments)}")
    for i, frag in enumerate(fragments, 1):
        print(f"\n=== Фрагмент {i} ===")
        print(frag)
        print("=" * 50)


def run_search(args: argparse.Namespace) -> bool:
    """
    Выполняет поиск фрагментов на основе аргументов.
    Возвращает True, если хотя бы один фрагмент найден, иначе False.
    """
    # Определяем данные для поиска
    if args.test:
        search_data = get_test_data()
    else:
        search_data = {
            args.url: [(args.label, args.value)]
        }
    
    all_fragments = []
    
    if args.selenium:
        driver = create_driver(headless=False)
        try:
            for url, pairs in search_data.items():
                if args.verbose:
                    print(f"\n🔍 Проверка URL: {url}")
                driver.get(url)
                for label, value in pairs:
                    if args.verbose:
                        print(f"\n=== Поиск пары: '{label}' – '{value}' ===")
                    fragments = search_with_selenium(
                        driver,
                        url,
                        label,
                        value,
                        exact_label=args.exact,
                        exact_value=args.exact,
                        case_sensitive=args.case_sensitive,
                        all_matches=args.all_matches,
                        verbose=args.verbose,
                        search_mode=args.search_mode,
                    )
                    all_fragments.extend(fragments)
        finally:
            driver.quit()
    else:
        for url, pairs in search_data.items():
            if args.verbose:
                print(f"\n🔍 Проверка URL: {url}")
            for label, value in pairs:
                if args.verbose:
                    print(f"\n=== Поиск пары: '{label}' – '{value}' ===")
                fragments = search_with_requests(
                    url,
                    label,
                    value,
                    exact_label=args.exact,
                    exact_value=args.exact,
                    case_sensitive=args.case_sensitive,
                    all_matches=args.all_matches,
                    verbose=args.verbose,
                    search_mode=args.search_mode,
                )
                all_fragments.extend(fragments)
    
    if not all_fragments:
        print("❌ Фрагменты не найдены.")
        if not args.verbose:
            print("💡 Попробуйте запустить с параметром --verbose, чтобы увидеть отладочную информацию.")
        return False
    
    print_fragments(all_fragments)
    return True


def main() -> None:
    args = parse_arguments()
    try:
        success = run_search(args)
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()