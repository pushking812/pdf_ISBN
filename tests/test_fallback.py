#!/usr/bin/env python3
"""
Тестирование fallback-генерации паттерна для пустых меток.
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

# Фрагмент HTML без классов и id
html_fragment = '''
<div>
    <h1>Многомерный анализ данных на Python</h1>
    <span>Какой-то дополнительный текст</span>
</div>
'''

parse_frags = [
    ('https://example.com', '', 'Многомерный анализ данных на Python', [html_fragment])
]

print("=== Тестирование fallback с пустым label (нет классов) ===")
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