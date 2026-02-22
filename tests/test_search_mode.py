from html_fragment import extract_common_parent_html


def test_search_mode_text_and_element_simple():
    html = """
    <li class="bookDataRow_item__Bh44I">
        <span class="bookDataRow_point__JI5op">Год издания<!-- -->:</span>
        <span class="bookDataRow_value__0qIpl">
            <div>
                <span class="book_value1__9QgSy" itemprop="copyrightYear">2022</span>
            </div>
        </span>
    </li>
    """

    # Режим text: ищем текстовые узлы
    fr_text = extract_common_parent_html(
        html, "Год издания:", "2022", verbose=False, search_mode="text"
    )
    assert len(fr_text) == 1

    # Режим element: ищем элементы по полному тексту
    fr_elem = extract_common_parent_html(
        html, "Год издания:", "2022", verbose=False, search_mode="element"
    )
    assert len(fr_elem) == 1


def test_search_mode_with_formatting_tags():
    html2 = """
    <div>
        <span>Год<strong>издания</strong>:</span>
        <p>2022</p>
    </div>
    """
    # В text-режиме label собирается из текстовых узлов с форматированием — должен сработать
    fr_text2 = extract_common_parent_html(
        html2, "Год издания:", "2022", verbose=False, search_mode="text"
    )
    assert len(fr_text2) == 1

    # В element-режиме полный текст тега span без нормализации пробелов — реализация find_elements_by_text нормализует,
    # поэтому тоже должен сработать
    fr_elem2 = extract_common_parent_html(
        html2, "Год издания:", "2022", verbose=False, search_mode="element"
    )
    assert len(fr_elem2) == 1
