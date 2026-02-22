#!/usr/bin/env python3
"""
Тестирование исправлений на примере пользователя.
"""
import sys
sys.path.insert(0, '.')

from debug_selectors import generate_pattern, extract_value
import argparse

# Создаём объект аргументов с нужными параметрами
args = argparse.Namespace(
    search_mode='element',
    exact=False,
    case_sensitive=False,
    verbose=True
)

# Фрагмент, аналогичный предоставленному пользователем (только h1 и span)
html_fragment = '''
<h1 class="book_PageTitle__2I49f" itemprop="name">Многомерный анализ данных на Python</h1>
<span>Какой-то дополнительный текст</span>
'''

parse_frags = [
    ('https://example.com', '', 'Многомерный анализ данных на Python', [html_fragment])
]

print("=== Генерация паттерна для примера пользователя ===")
try:
    patterns = generate_pattern(parse_frags, args)
except Exception as e:
    print(f"Ошибка генерации: {e}")
    sys.exit(1)

print("\nСгенерированные паттерны:")
for i, p in enumerate(patterns):
    print(f"  {i}: {p['type']} -> {p['selector']}")

# Тестируем извлечение значения из того же HTML
print("\n=== Извлечение значения с использованием паттерна ===")
pattern = patterns[0]
html = html_fragment  # тот же HTML
try:
    value = extract_value(html, pattern, use_selenium=False)
    print(f"Извлечённое значение: {value!r}")
    expected = "Многомерный анализ данных на Python"
    if value == expected:
        print("✅ Тест пройден: значение совпадает с ожидаемым.")
    else:
        print(f"❌ Тест не пройден: ожидалось {expected!r}, получено {value!r}.")
except Exception as e:
    print(f"Ошибка извлечения: {e}")
    import traceback
    traceback.print_exc()