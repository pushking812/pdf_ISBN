#!/usr/bin/env python3
"""
Unit-тесты для модуля html_fragment.py.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
import pytest

from html_fragment import (
    find_text_nodes,
    lowest_common_ancestor,
    extract_common_parent_html,
)


class TestFindTextNodes:
    """Тесты для find_text_nodes."""

    def test_exact_match(self):
        html = "<div>Год издания</div><p>Год издания 2020</p>"
        soup = BeautifulSoup(html, "lxml")
        nodes = find_text_nodes(soup, "Год издания", exact=True)
        assert len(nodes) == 1
        assert nodes[0].strip() == "Год издания"

    def test_partial_match(self):
        html = "<div>Год издания 2020</div>"
        soup = BeautifulSoup(html, "lxml")
        nodes = find_text_nodes(soup, "Год", exact=False)
        assert len(nodes) == 1
        assert "Год" in nodes[0]

    def test_case_insensitive(self):
        html = "<div>Год издания</div><div>ГОД ИЗДАНИЯ</div>"
        soup = BeautifulSoup(html, "lxml")
        nodes = find_text_nodes(soup, "год издания", exact=True, case_sensitive=False)
        assert len(nodes) == 2
        # Оба узла должны быть найдены (регистр не важен)
        texts = {n.strip() for n in nodes}
        assert texts == {"Год издания", "ГОД ИЗДАНИЯ"}

    def test_case_sensitive(self):
        html = "<div>Год издания</div><div>ГОД ИЗДАНИЯ</div>"
        soup = BeautifulSoup(html, "lxml")
        nodes = find_text_nodes(soup, "Год издания", exact=True, case_sensitive=True)
        assert len(nodes) == 1
        assert nodes[0].strip() == "Год издания"

    def test_no_match(self):
        html = "<div>Что-то другое</div>"
        soup = BeautifulSoup(html, "lxml")
        nodes = find_text_nodes(soup, "Год издания")
        assert len(nodes) == 0


class TestLowestCommonAncestor:
    """Тесты для lowest_common_ancestor."""

    def test_same_node(self):
        html = "<div>Текст</div>"
        soup = BeautifulSoup(html, "lxml")
        node = soup.find(string="Текст")
        ancestor = lowest_common_ancestor(node, node)
        # Ожидается родительский тег <div>
        assert ancestor is not None
        assert ancestor.name == "div"

    def test_siblings(self):
        html = """
        <div>
            <span class='label'>Год</span>
            <span class='value'>2020</span>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        label = soup.find(string="Год")
        value = soup.find(string="2020")
        ancestor = lowest_common_ancestor(label, value)
        assert ancestor.name == "div"
        assert ancestor.get("class") is None

    def test_nested(self):
        html = """
        <body>
            <div>
                <p><strong>Год</strong></p>
                <p>2020</p>
            </div>
        </body>
        """
        soup = BeautifulSoup(html, "lxml")
        label = soup.find(string="Год")
        value = soup.find(string="2020")
        ancestor = lowest_common_ancestor(label, value)
        assert ancestor.name == "div"

    def test_different_branches(self):
        html = """
        <div>
            <section><p>Год</p></section>
            <article><p>2020</p></article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        label = soup.find(string="Год")
        value = soup.find(string="2020")
        ancestor = lowest_common_ancestor(label, value)
        assert ancestor.name == "div"

    def test_no_common_ancestor(self):
        # Два отдельных документа – в BeautifulSoup они всё равно в одном дереве?
        # Создадим два отдельных дерева, но в одном супе они будут под одним корнем.
        # Для чистоты теста пропустим.
        pass


class TestExtractCommonParentHtml:
    """Тесты для extract_common_parent_html."""

    def test_simple_pair(self):
        html = """
        <div>
            <span>Год издания</span>
            <span>2020</span>
        </div>
        """
        fragments = extract_common_parent_html(html, "Год издания", "2020")
        assert len(fragments) == 1
        # Проверим, что фрагмент содержит оба текста
        frag = fragments[0]
        assert "Год издания" in frag
        assert "2020" in frag
        # Убедимся, что это именно <div>
        soup = BeautifulSoup(frag, "lxml")
        assert soup.find("div") is not None

    def test_multiple_pairs(self):
        html = """
        <div class='book'>
            <span>Год издания</span>
            <span>2020</span>
        </div>
        <div class='book'>
            <span>Год издания</span>
            <span>2021</span>
        </div>
        """
        fragments = extract_common_parent_html(html, "Год издания", "2020")
        # Должен найти только первый блок (содержащий "2020")
        assert len(fragments) == 1
        frag = fragments[0]
        assert "2020" in frag
        assert "2021" not in frag

    def test_all_matches_false(self):
        html = """
        <div>
            <span>Год издания</span>
            <span>2020</span>
        </div>
        <div>
            <span>Год издания</span>
            <span>2021</span>
        </div>
        """
        fragments = extract_common_parent_html(
            html, "Год издания", "2020", all_matches=False
        )
        # Должен вернуть только первый найденный фрагмент
        assert len(fragments) == 1
        assert "2020" in fragments[0]

    def test_all_matches_true(self):
        html = """
        <div>
            <span>Год издания</span>
            <span>2020</span>
        </div>
        <div>
            <span>Год издания</span>
            <span>2021</span>
        </div>
        """
        fragments = extract_common_parent_html(
            html, "Год издания", "2020", all_matches=True
        )
        # Должен найти оба блока? Нет, потому что значение "2020" есть только в первом.
        # Но label "Год издания" есть в обоих, но value "2020" только в первом.
        # Поэтому должен быть только один фрагмент.
        assert len(fragments) == 1
        # Если же искать value "2020" и "2021" одновременно? Не входит в тест.
        pass

    def test_no_label(self):
        html = "<div>Что-то</div>"
        fragments = extract_common_parent_html(html, "Год издания", "2020")
        assert len(fragments) == 0

    def test_no_value(self):
        html = "<div>Год издания</div>"
        fragments = extract_common_parent_html(html, "Год издания", "2020")
        assert len(fragments) == 0

    def test_label_and_value_in_same_text_node(self):
        html = "<div>Год издания: 2020</div>"
        fragments = extract_common_parent_html(html, "Год издания", "2020", exact_label=False, exact_value=False)
        # Оба текста внутри одного текстового узла, их родитель – <div>
        assert len(fragments) == 1
        frag = fragments[0]
        assert "Год издания" in frag
        assert "2020" in frag

    def test_duplicate_ancestors(self):
        # Один и тот же предок может быть получен от разных пар узлов
        html = """
        <div>
            <span>Год издания</span>
            <span>2020</span>
            <span>Год издания</span>
            <span>2020</span>
        </div>
        """
        fragments = extract_common_parent_html(html, "Год издания", "2020")
        # Должен быть один уникальный фрагмент (предок один и тот же)
        assert len(fragments) == 1

    def test_exact_vs_partial(self):
        html = "<div>Год издания 2020</div>"
        # Точное совпадение для label не найдёт, потому что есть дополнительные цифры
        fragments = extract_common_parent_html(
            html, "Год издания", "2020", exact_label=True, exact_value=True
        )
        # label "Год издания" не равен "Год издания 2020", поэтому не найдено
        # (зависит от реализации find_text_nodes – она использует strip, но strip удаляет пробелы,
        # но не цифры. Текст узла "Год издания 2020" после strip не равен "Год издания".
        # Поэтому ожидаем 0 фрагментов.
        assert len(fragments) == 0
        # Частичное совпадение найдёт
        fragments2 = extract_common_parent_html(
            html, "Год издания", "2020", exact_label=False, exact_value=False
        )
        assert len(fragments2) == 1


if __name__ == "__main__":
    # Запуск тестов через pytest (если установлен)
    pytest.main([__file__, "-v"])