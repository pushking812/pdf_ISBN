#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка скрапинга book.ru по ISBN 9785406097656."""

import sys
sys.path.insert(0, '.')

from config import ScraperConfig
from scraper import search_multiple_books

if __name__ == "__main__":
    config = ScraperConfig(
        headless=False,
        skip_main_page=True,
        use_fast_selectors=True,
        wait_product_link=10,
        delay_after_main=(0.5, 1.0),
        delay_after_search=(0.8, 1.5),
        delay_after_click=(0.5, 1.0),
        poll_interval=0.5,
        no_product_phrases=["Похоже, у нас такого нет", "ничего не нашлось"],
        max_tabs=1,
        rate_limit_phrases=[],
        rate_limit_initial_delay=10.0,
        rate_limit_coef_start=1.0,
        rate_limit_coef_step=0.2,
        rate_limit_coef_max=3.0,
        handle_rate_limit=False,
        keep_browser_open=False,
        verbose=True,
        api_max_concurrent=1,
    )
    isbn_list = ["9785406097656"]
    print(f"Запуск скрапинга для ISBN {isbn_list[0]} на book.ru...")
    results = search_multiple_books(isbn_list, config)
    print("Результаты:")
    for i, res in enumerate(results):
        if res:
            print(f"  Найдено: {res.get('title')}, автор(ы): {res.get('authors')}, страницы: {res.get('pages')}, год: {res.get('year')}, источник: {res.get('source')}")
        else:
            print(f"  Не найдено.")
    sys.exit(0)