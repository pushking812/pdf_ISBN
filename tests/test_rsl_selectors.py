#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест селекторов для ресурса РГБ.
Проверяет поиск ссылки на книгу в search_result_rsl.html
и извлечение данных из book_page_rsl.html.
"""

from bs4 import BeautifulSoup
from resources import _rsl_resource
from scraper import parse_book_page_for_resource


class DummyDriver:
    def __init__(self, html: str, url: str):
        self.page_source = html
        self.current_url = url


def test_search_result():
    """Проверка находки первой ссылки на книгу в search_result_rsl.html."""
    with open("search_result_rsl.html", "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "lxml")
    resource = _rsl_resource()
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
    """Проверка извлечения данных из book_page_rsl.html."""
    with open("book_page_rsl.html", "r", encoding="utf-8") as f:
        html = f.read()
    driver = DummyDriver(html, "https://search.rsl.ru/ru/record/01011142728")
    resource = _rsl_resource()
    data = parse_book_page_for_resource(driver, resource)
    print("Результат парсинга страницы книги:")
    for key, value in data.items():
        print(f"  {key}: {value}")
    # Проверяем ожидаемые значения
    expected_title = "Структуры данных в Python: начальный курс"
    expected_author = "Шихи, Дональд Р."
    expected_pages = "185"
    expected_year = "2022"
    
    if data.get("title") == expected_title:
        print(f"✅ Заголовок корректный: {data['title']}")
    else:
        print(f"❌ Заголовок не совпадает. Ожидалось: '{expected_title}', получено: '{data.get('title')}'")
    
    if data.get("authors") and data["authors"][0] == expected_author:
        print(f"✅ Автор корректный: {data['authors'][0]}")
    else:
        print(f"❌ Автор не совпадает. Ожидалось: '{expected_author}', получено: '{data.get('authors')}'")
    
    if data.get("pages") == expected_pages:
        print(f"✅ Страницы корректные: {data['pages']}")
    else:
        print(f"❌ Страницы не совпадают. Ожидалось: '{expected_pages}', получено: '{data.get('pages')}'")
    
    if data.get("year") == expected_year:
        print(f"✅ Год корректный: {data['year']}")
    else:
        print(f"❌ Год не совпадает. Ожидалось: '{expected_year}', получено: '{data.get('year')}'")
    
    return data


if __name__ == "__main__":
    print("=== Тест поиска ссылки в search_result_rsl.html ===")
    test_search_result()
    print("\n=== Тест парсинга book_page_rsl.html ===")
    test_book_page()