import pytest
from lxml import etree
import requests


@pytest.mark.network
def test_xpath_value_extraction_from_rsl_page():
    url = "https://search.rsl.ru/ru/record/01010115385"
    # Минимальные заголовки и таймаут для стабильности
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    html = resp.text

    selector = "//*[./th[contains(text(), 'Автор')]]//th[contains(text(), 'Автор')]/following-sibling::td"
    tree = etree.HTML(html)
    elements = tree.xpath(selector)
    assert len(elements) >= 1

    element = elements[0]
    text = element.xpath("string()")
    value = text if isinstance(text, str) else (text[0] if text else "")
    assert value
