from html_fragment import find_elements_by_text, find_text_nodes
from bs4 import BeautifulSoup


def test_find_helpers_exact_and_partial():
    html = '<tr><th>Физическое описание</th><td>192 с. : ил.; 26 см</td></tr>'
    soup = BeautifulSoup(html, 'lxml')

    # partial match: должен найти <td> по подстроке
    nodes = find_elements_by_text(soup, '192 с.', exact=False, case_sensitive=False)
    assert len(nodes) == 1
    assert nodes[0].name == 'td'

    # partial match по текстовому узлу внутри td
    nodes2 = find_text_nodes(soup, '192 с.', exact=False, case_sensitive=False)
    assert len(nodes2) == 1
    assert '192 с.' in nodes2[0]

    # exact=True: полный текст td не равен '192 с.' -> не должен найти элемент
    nodes3 = find_elements_by_text(soup, '192 с.', exact=True, case_sensitive=False)
    assert len(nodes3) == 0

    # Полный текст td содержит целую строку
    td = soup.find('td')
    assert td.get_text() == '192 с. : ил.; 26 см'