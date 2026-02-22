from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from config import ScraperConfig


def _chitai_gorod_resource(base_url: str, config: ScraperConfig) -> Dict[str, Any]:
    """Читай-город: селекторы под текущий сайт."""
    use_fast = getattr(config, "use_fast_selectors", False)
    return {
        "id": "chitai-gorod",
        "name": "Читай-город",
        "base_url": base_url,
        "search_url_template": f"{base_url.rstrip('/')}/search?phrase={{isbn}}",
        "product_link_selectors": [
            'a[href^="/product/"]',
            "a.product-card__title",
            "a.product-title",
            ".catalog-item a",
        ]
        if not use_fast
        else ['a[href^="/product/"]'],
        "no_product_phrases": getattr(config, "no_product_phrases", None)
        or ["Похоже, у нас такого нет", "ничего не нашлось"],
        "title_selectors": [
            "h1.product-detail-page__title",
            "h1.product-title",
            'h1[itemprop="name"]',
            ".product__title h1",
            "h1",
        ],
        "author_selectors": [
            ".product-authors a",
            ".product-author a",
            'a[itemprop="author"]',
            ".product-info__author",
            ".authors-list a",
        ],
        "pages_selectors": [
            'span[itemprop="numberOfPages"] span',
            '.product-properties-item span[itemprop="numberOfPages"]',
        ],
        "year_selectors": [
            'span[itemprop="datePublished"] span',
            '.product-properties-item span[itemprop="datePublished"]',
        ],
        "properties_item_class": "product-properties-item",
        "properties_title_class": "product-properties-item__title",
        "properties_content_class": "product-properties-item__content",
        "source_label": "Читай-город",
        "need_main_page": not getattr(config, "skip_main_page", True),
        "city_modal_xpath": "//button[contains(text(), 'Да, я здесь')]",
    }


def _book_ru_resource() -> Dict[str, Any]:
    """Book.ru: поиск по ISBN."""

    def custom_parser(driver, resource):
        import json
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(driver.page_source, "lxml")
        
        # Проверка на страницу "ничего не найдено"
        no_product_phrases = resource.get("no_product_phrases", [])
        page_text = soup.get_text().lower()
        if any(phrase.lower() in page_text for phrase in no_product_phrases if phrase):
            return None
        
        # Пытаемся извлечь данные из JSON скрипта __NEXT_DATA__
        script = soup.find("script", id="__NEXT_DATA__")
        if script:
            try:
                data = json.loads(script.string)
                # Путь к данным книги
                server_data = data.get("props", {}).get("pageProps", {}).get("serverDataBook", {})
                if server_data.get("result") == 1:
                    items = server_data.get("item", [])
                    if items:
                        book = items[0]  # первая книга в списке
                        title = book.get("name", "").strip()
                        authors = []
                        # Автор может быть в поле "author" (строка)
                        author_str = book.get("author")
                        if author_str:
                            authors = [author_str.strip()]
                        pages = book.get("pages")
                        if pages is not None:
                            pages = str(pages)
                        year = book.get("year", "").strip()
                        isbn = book.get("isbn", "").strip()
                        # Если ISBN не найден, можно использовать EAN
                        if not isbn:
                            isbn = book.get("ean", "").strip()
                        
                        return {
                            "title": title or "Не удалось определить название",
                            "authors": authors or ["Неизвестный автор"],
                            "pages": pages or "не указано",
                            "year": year or "не указан",
                            "url": driver.current_url,
                            "source": resource.get("source_label", "Book.ru"),
                        }
                    else:
                        # items пуст -> книга не найдена
                        return None
                else:
                    # result != 1 -> книга не найдена или ошибка
                    return None
            except (json.JSONDecodeError, KeyError, IndexError):
                pass  # Проваливаемся на стандартный парсер
        
        # Fallback: стандартный парсинг через селекторы
        title = None
        for sel in resource.get("title_selectors", []):
            elem = soup.select_one(sel)
            if elem:
                if elem.name == "meta":
                    title = elem.get("content", "").strip()
                else:
                    title = elem.get_text(strip=True)
                break
        
        authors = []
        for sel in resource.get("author_selectors", []):
            elems = soup.select(sel)
            if elems:
                authors = [a.get_text(strip=True) for a in elems if a.get_text(strip=True)]
                break
        
        pages = None
        for sel in resource.get("pages_selectors", []):
            elem = soup.select_one(sel)
            if elem:
                pages = elem.get_text(strip=True)
                break
        
        year = None
        for sel in resource.get("year_selectors", []):
            elem = soup.select_one(sel)
            if elem:
                year = elem.get_text(strip=True)
                break
        
        # Дополнительный поиск в свойствах
        if resource.get("properties_item_class"):
            for li in soup.find_all("li", class_=resource["properties_item_class"]):
                title_elem = li.find("span", class_=resource.get("properties_title_class", ""))
                content_elem = li.find("span", class_=resource.get("properties_content_class", ""))
                if title_elem and content_elem:
                    text = title_elem.get_text(strip=True).lower()
                    if not pages and ("страниц" in text or "стр." in text or "объем" in text):
                        pages = content_elem.get_text(strip=True)
                    if not year and "год" in text:
                        year_span = content_elem.find("span", itemprop="copyrightYear")
                        if year_span and year_span.get_text(strip=True):
                            year = year_span.get_text(strip=True)
                        else:
                            year = content_elem.get_text(strip=True)
        
        return {
            "title": title or "Не удалось определить название",
            "authors": authors or ["Неизвестный автор"],
            "pages": pages or "не указано",
            "year": year or "не указан",
            "url": driver.current_url,
            "source": resource.get("source_label", "Book.ru"),
        }

    return {
        "id": "book-ru",
        "name": "Book.ru",
        "base_url": "https://book.ru",
        "search_url_template": "https://book.ru/search?q={isbn}",
        "product_link_selectors": [
            'a[data-test-id="bookCardLink"]',
            'a[href*="/book/"]',
        ],
        "no_product_phrases": [
            "ничего не найдено",
            "ничего не найдено по запросу",
            "по вашему запросу ничего не найдено",
            "Книги / Новинки",
            # "Новинки" убрано, т.к. это не фраза "ничего не найдено"
        ],
        "title_selectors": ["h1", 'meta[property="og:title"]'],
        "author_selectors": ['[itemprop="author"]'],
        "pages_selectors": [],
        "year_selectors": [],
        "properties_item_class": "bookDataRow_item__Bh44I",
        "properties_title_class": "bookDataRow_point__JI5op",
        "properties_content_class": "bookDataRow_value__0qIpl",
        "source_label": "Book.ru",
        "need_main_page": False,
        "city_modal_xpath": None,
        "custom_parser": custom_parser,
    }


def _rsl_resource() -> Dict[str, Any]:
    """РГБ (Российская государственная библиотека): поиск по ISBN."""

    def custom_parser(driver, resource):
        import re
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(driver.page_source, "lxml")
        
        # Поиск таблицы с описанием книги
        table = soup.find("table", class_="card-descr-table")
        if not table:
            # Если таблицы нет, возможно, это страница поиска, пытаемся найти ссылку на книгу
            # или используем старый метод как fallback
            return {
                "title": "Не удалось определить название",
                "authors": ["Неизвестный автор"],
                "pages": "не указано",
                "year": "не указан",
                "url": driver.current_url,
                "source": resource.get("source_label", "РГБ"),
            }
        
        # Инициализируем переменные
        title = None
        authors = []
        pages = None
        year = None
        isbn = None
        
        # Проходим по строкам таблицы
        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if not th or not td:
                continue
            header = th.get_text(strip=True)
            value = td.get_text(strip=True)
            
            if header == "Автор":
                authors = [value]
            elif header == "Заглавие":
                title = value
            elif header == "ISBN":
                # Извлекаем ISBN из строки, убирая префикс "ISBN"
                isbn_match = re.search(r"ISBN\s*([\d\-]+)", value)
                if isbn_match:
                    isbn = isbn_match.group(1)
            elif header == "Выходные данные":
                # Пытаемся извлечь год из выходных данных
                year_match = re.search(r"(\d{4})", value)
                if year_match:
                    year = year_match.group(1)
            elif header == "Физическое описание":
                # Извлекаем количество страниц
                pages_match = re.search(r"(\d+)\s+с\.", value)
                if pages_match:
                    pages = pages_match.group(1)
            elif header == "Дата поступления в ЭК РГБ":
                # Если года ещё нет, можно попробовать извлечь год из даты
                if not year:
                    year_match = re.search(r"(\d{4})", value)
                    if year_match:
                        year = year_match.group(1)
        
        # Если название не найдено, пытаемся получить из тега h1 или другого селектора
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
        
        # Если авторы не найдены, пытаемся найти по другим селекторам
        if not authors:
            author_elem = soup.find("b", class_="js-item-authorinfo")
            if author_elem:
                authors = [author_elem.get_text(strip=True).rstrip(".")]
        
        return {
            "title": title or "Не удалось определить название",
            "authors": authors or ["Неизвестный автор"],
            "pages": pages or "не указано",
            "year": year or "не указан",
            "url": driver.current_url,
            "source": resource.get("source_label", "РГБ"),
        }

    return {
        "id": "rsl",
        "name": "РГБ",
        "base_url": "https://search.rsl.ru",
        "search_url_template": "https://search.rsl.ru/ru/search?q={isbn}",
        "product_link_selectors": [
            "a.rsl-modal[href^='/ru/record/']",
            "div.rsl-itemaction-description-link a",
        ],
        "no_product_phrases": [
            "ничего не найдено",
            "по вашему запросу ничего не найдено",
            "не найдено",
        ],
        "title_selectors": [],
        "author_selectors": [],
        "pages_selectors": [],
        "year_selectors": [],
        "properties_item_class": None,
        "properties_title_class": None,
        "properties_content_class": None,
        "source_label": "РГБ",
        "need_main_page": False,
        "city_modal_xpath": None,
        "custom_parser": custom_parser,
    }


def get_scraper_resources(config: ScraperConfig) -> List[Dict[str, Any]]:
    """Возвращает список зарегистрированных ресурсов для скрапинга."""
    return [
        _chitai_gorod_resource(
            getattr(config, "base_url", "https://www.chitai-gorod.ru"), config
        ),
        _book_ru_resource(),
        _rsl_resource(),
    ]


def get_resource_by_url(url: str, config: ScraperConfig = None) -> Optional[Dict[str, Any]]:
    """
    Возвращает ресурс (словарь с селекторами), соответствующий переданному URL.
    Если конфиг не передан, создаётся конфиг по умолчанию.
    """
    from urllib.parse import urlparse
    
    if config is None:
        from config import ScraperConfig
        config = ScraperConfig()
    
    resources = get_scraper_resources(config)
    parsed_url = urlparse(url)
    url_domain = parsed_url.netloc.lower()
    
    for resource in resources:
        resource_url = resource.get("base_url")
        if not resource_url:
            continue
        parsed_resource = urlparse(resource_url)
        resource_domain = parsed_resource.netloc.lower()
        # Сравниваем домены (можно также учитывать поддомены)
        if url_domain == resource_domain or url_domain.endswith('.' + resource_domain):
            return resource
        # Дополнительно проверяем, содержит ли URL базовый URL (для учёта пути)
        if url.startswith(resource_url):
            return resource
    
    return None
