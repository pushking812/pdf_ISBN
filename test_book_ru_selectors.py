#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест селекторов для ресурса Book.ru.
Проверяет поиск ссылки на книгу в search_result.html
и извлечение данных из book_page.html.
"""

from bs4 import BeautifulSoup
from web_scraper_isbn import _book_ru_resource, parse_book_page_for_resource

class DummyDriver:
    def __init__(self, html: str, url: str):
        self.page_source = html
        self.current_url = url

def test_search_result():
    """Проверка находки первой ссылки на книгу в search_result.html."""
    with open("search_result.html", "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "lxml")
    resource = _book_ru_resource()
    link = None
    for sel in resource["product_link_selectors"]:
        elems = soup.select(sel)
        if elems:
            link = elems[0].get("href")
            print(f"Найден селектор: '{sel}', href = {link}")
            break
    if not link:
        print("❌ Ссылка не найдена ни одним селектором.")
    return link

def test_book_page():
    """Проверка извлечения данных из book_page.html."""
    with open("book_page.html", "r", encoding="utf-8") as f:
        html = f.read()
    driver = DummyDriver(html, "https://book.ru/book/943665")
    resource = _book_ru_resource()
    data = parse_book_page_for_resource(driver, resource)
    print("Результат парсинга страницы книги:")
    for key, value in data.items():
        print(f"  {key}: {value}")
    return data

if __name__ == "__main__":
    print("=== Тест поиска ссылки в search_result.html ===")
    test_search_result()
    print("\n=== Тест парсинга book_page.html ===")
    test_book_page()