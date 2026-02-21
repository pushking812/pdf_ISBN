#!/usr/bin/env python3
"""
Тестирование новых режимов search_mode.
"""
import sys
sys.path.insert(0, '.')

from html_fragment import extract_common_parent_html

html = '''
<li class="bookDataRow_item__Bh44I">
    <span class="bookDataRow_point__JI5op">Год издания<!-- -->:</span>
    <span class="bookDataRow_value__0qIpl">
        <div>
            <span class="book_value1__9QgSy" itemprop="copyrightYear">2022</span>
            <div class="book_izdRow__NBM_r">
                <div class="book_izdName1__SgqHu">Новое издание:&nbsp;</div>
                <div class="book_years__lTH33"><a target="_blank" href="/book/955467">2025</a></div>
            </div>
        </div>
    </span>
</li>
'''

print("=== Режим 'text' (по умолчанию) ===")
fragments = extract_common_parent_html(html, "Год издания:", "2022", verbose=True, search_mode="text")
print(f"Найдено фрагментов: {len(fragments)}")
for f in fragments:
    print(f[:200])

print("\n=== Режим 'element' ===")
fragments = extract_common_parent_html(html, "Год издания:", "2022", verbose=True, search_mode="element")
print(f"Найдено фрагментов: {len(fragments)}")
for f in fragments:
    print(f[:200])

print("\n=== Режим 'cleaned' ===")
fragments = extract_common_parent_html(html, "Год издания:", "2022", verbose=True, search_mode="cleaned")
print(f"Найдено фрагментов: {len(fragments)}")
for f in fragments:
    print(f[:200])

# Также тест с тегами форматирования
html2 = '''
<div>
    <span>Год<strong>издания</strong>:</span>
    <p>2022</p>
</div>
'''
print("\n=== HTML с тегами форматирования ===")
fragments = extract_common_parent_html(html2, "Год издания:", "2022", verbose=True, search_mode="text")
print(f"Режим 'text': {len(fragments)}")
fragments = extract_common_parent_html(html2, "Год издания:", "2022", verbose=True, search_mode="element")
print(f"Режим 'element': {len(fragments)}")
fragments = extract_common_parent_html(html2, "Год издания:", "2022", verbose=True, search_mode="cleaned")
print(f"Режим 'cleaned': {len(fragments)}")