#!/usr/bin/env python3
"""
Скрипт для отладки выбора ancestor при пустом label.
"""
import sys
sys.path.insert(0, '.')

from debug_selectors import generate_pattern
import argparse

# Создаём объект аргументов с нужными параметрами
args = argparse.Namespace(
    search_mode='element',
    exact=False,
    case_sensitive=False,
    verbose=True
)

# Фрагмент HTML, аналогичный тому, что был в выводе пользователя
html_fragment = '''
<div class="book_self__lezJq">
    <h1 class="book_PageTitle__2I49f" itemprop="name">Многомерный анализ данных на Python</h1>
    <span>Какой-то дополнительный текст</span>
</div>
'''

# Эмулируем структуру parse_frags, как в debug_selectors.py
parse_frags = [
    ('https://example.com', '', 'Многомерный анализ данных на Python', [html_fragment])
]

print("=== Тестирование generate_pattern с пустым label ===")
print(f"HTML фрагмент:\n{html_fragment}")
try:
    patterns = generate_pattern(parse_frags, args)
    print("\nРезультат:")
    for p in patterns:
        print(f"  Тип: {p['type']}")
        print(f"  Селектор: {p['selector']}")
        print(f"  Атрибут: {p['attribute']}")
except Exception as e:
    print(f"Ошибка: {e}")
    import traceback
    traceback.print_exc()