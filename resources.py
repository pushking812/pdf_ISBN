from typing import Dict, Any, List
from config import ScraperConfig

def _chitai_gorod_resource(base_url: str, config: ScraperConfig) -> Dict[str, Any]:
    """Читай-город: селекторы под текущий сайт."""
    use_fast = getattr(config, 'use_fast_selectors', False)
    return {
        "id": "chitai-gorod",
        "name": "Читай-город",
        "base_url": base_url,
        "search_url_template": f"{base_url.rstrip('/')}/search?phrase={{isbn}}",
        "product_link_selectors": ['a[href^="/product/"]', 'a.product-card__title', 'a.product-title', '.catalog-item a'] if not use_fast else ['a[href^="/product/"]'],
        "no_product_phrases": getattr(config, 'no_product_phrases', None) or ["Похоже, у нас такого нет", "ничего не нашлось"],
        "title_selectors": ['h1.product-detail-page__title', 'h1.product-title', 'h1[itemprop=\"name\"]', '.product__title h1', 'h1'],
        "author_selectors": ['.product-authors a', '.product-author a', 'a[itemprop=\"author\"]', '.product-info__author', '.authors-list a'],
        "pages_selectors": ['span[itemprop=\"numberOfPages\"] span', '.product-properties-item span[itemprop=\"numberOfPages\"]'],
        "year_selectors": ['span[itemprop=\"datePublished\"] span', '.product-properties-item span[itemprop=\"datePublished\"]'],
        "properties_item_class": "product-properties-item",
        "properties_title_class": "product-properties-item__title",
        "properties_content_class": "product-properties-item__content",
        "source_label": "Читай-город",
        "need_main_page": not getattr(config, 'skip_main_page', True),
        "city_modal_xpath": "//button[contains(text(), 'Да, я здесь')]",  
    }

def _book_ru_resource() -> Dict[str, Any]:
    """Book.ru: поиск по ISBN."""
    return {
        "id": "book-ru",
        "name": "Book.ru",
        "base_url": "https://book.ru",
        "search_url_template": "https://book.ru/search?q={isbn}&area=isbn",
        "product_link_selectors": [
            'a[data-test-id=\"bookCardLink\"]',
            'a[href*=\"/book/\"]'
        ],
        "no_product_phrases": ["ничего не найдено", "ничего не найдено по запросу", "по вашему запросу ничего не найдено"],
        "title_selectors": ['h1', 'meta[property=\"og:title\"]'],
        "author_selectors": ['[itemprop=\"author\"]'],
        "pages_selectors": [],
        "year_selectors": [],
        "properties_item_class": "bookDataRow_item__Bh44I",
        "properties_title_class": "bookDataRow_point__JI5op",
        "properties_content_class": "bookDataRow_value__0qIpl",
        "source_label": "Book.ru",
        "need_main_page": False,
        "city_modal_xpath": None,
    }

def get_scraper_resources(config: ScraperConfig) -> List[Dict[str, Any]]:
    """Возвращает список зарегистрированных ресурсов для скрапинга."""
    return [
        _chitai_gorod_resource(getattr(config, 'base_url', 'https://www.chitai-gorod.ru'), config),
        _book_ru_resource(),
    ]