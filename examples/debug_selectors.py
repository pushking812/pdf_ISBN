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
from typing import List

# Добавляем родительскую директорию в путь, чтобы импортировать html_fragment
sys.path.insert(0, "..")

from html_fragment import (
    extract_common_parent_from_url,
    extract_common_parent_from_driver,
)


def main():
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
        default = True,
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
        default = True,
    )
    parser.add_argument(
        "--search-mode",
        choices=["text", "element", "cleaned"],
        default="element",
        help="Режим поиска узлов: text (по текстовым узлам), element (по элементам с полным текстом), cleaned (очистка комментариев)",
    )
    args = parser.parse_args()

    try:
        if args.selenium:
            from drivers import create_chrome_driver
            from config import ScraperConfig
            config = ScraperConfig(headless=False)
            driver = create_chrome_driver(config)
            driver.get(args.url)
            fragments = extract_common_parent_from_driver(
                driver,
                args.label,
                args.value,
                exact_label=args.exact,
                exact_value=args.exact,
                case_sensitive=args.case_sensitive,
                all_matches=args.all_matches,
                verbose=args.verbose,
                search_mode=args.search_mode,
            )
            driver.quit()
        else:
            fragments = extract_common_parent_from_url(
                args.url,
                args.label,
                args.value,
                exact_label=args.exact,
                exact_value=args.exact,
                case_sensitive=args.case_sensitive,
                all_matches=args.all_matches,
                verbose=args.verbose,
                search_mode=args.search_mode,
            )

        if not fragments:
            print("❌ Фрагменты не найдены.")
            if not args.verbose:
                print("💡 Попробуйте запустить с параметром --verbose, чтобы увидеть отладочную информацию.")
            sys.exit(1)

        print(f"Найдено фрагментов: {len(fragments)}")
        for i, frag in enumerate(fragments, 1):
            print(f"\n=== Фрагмент {i} ===")
            print(frag)
            print("=" * 50)

    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()