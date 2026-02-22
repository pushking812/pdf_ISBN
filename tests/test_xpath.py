import sys
sys.path.append('.')
from lxml import etree
import requests

url = 'https://search.rsl.ru/ru/record/01010115385'
response = requests.get(url)
html = response.text
tree = etree.HTML(html)

xpath = "//*[./th[contains(text(), 'Автор')]]//th[contains(text(), 'Автор')]/following-sibling::td"
print(f"Testing XPath: {xpath}")
elements = tree.xpath(xpath)
print(f"Found {len(elements)} elements")
for i, el in enumerate(elements):
    print(f"Element {i}: {etree.tostring(el, encoding='unicode', method='html')}")
    print(f"Text: {el.text}")