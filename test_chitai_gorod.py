#!/usr/bin/env python3
"""
Тестирование улучшений на фрагментах chitai-gorod.ru.
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

# Фрагменты из вывода пользователя
fragments = [
    # 1. Пустой label, название книги
    ('https://www.chitai-gorod.ru/product/programmirovanie-na-python-v-primerah-i-zadachah-2832349', '', 'Программирование на Python в примерах и задачах', 
     ['<li class="breadcrumbs__item" style=""><!-- --><span class="global-link--line breadcrumbs__item breadcrumbs__item--span"><span class="breadcrumbs__item--last" style="max-width: calc(-1239px + 100vw);">Программирование на Python в примерах и задачах</span></span><!-- --></li>', 
      '<span class="global-link--line breadcrumbs__item breadcrumbs__item--span"><span class="breadcrumbs__item--last" style="max-width: calc(-1239px + 100vw);">Программирование на Python в примерах и задачах</span></span>', 
      '<span class="breadcrumbs__item--last" style="max-width: calc(-1239px + 100vw);">Программирование на Python в примерах и задачах</span>']),
    # 2. Пара "Год издания" – "2025"
    ('https://www.chitai-gorod.ru/product/programmirovanie-na-python-v-primerah-i-zadachah-2832349', 'Год издания', '2025', 
     ['<li class="product-properties-item"><span class="product-properties-item__title">Год издания <!-- --></span><span class="product-properties-item__content"><span class="" itemprop="datePublished"><!--[--><!--[--><span>2025</span><!-- --><!--]--><!--]--></span><!-- --></span></li>']),
    # 3. Пустой label, автор
    ('https://www.chitai-gorod.ru/product/programmirovanie-na-python-v-primerah-i-zadachah-2832349', '', 'Алексей Васильев', 
     ['<ul class="product-authors"><!--[--><li class="product-authors__link"><a class="global-link" href="/author/vasilev-aleksey-597580" itemprop="url">Алексей Васильев</a></li><!--]--></ul>', 
      '<li class="product-authors__link"><a class="global-link" href="/author/vasilev-aleksey-597580" itemprop="url">Алексей Васильев</a></li>', 
      '<a class="global-link" href="/author/vasilev-aleksey-597580" itemprop="url">Алексей Васильев</a>']),
    # 4. Пара "Количество страниц" – "616" (фрагмент не предоставлен, пропустим)
]

print("=== Тестирование улучшенной генерации паттернов для chitai-gorod.ru ===")
for i, (url, label, value, html_list) in enumerate(fragments):
    print(f"\n--- Тест {i+1}: label={label!r}, value={value!r} ---")
    parse_frags = [(url, label, value, html_list)]
    try:
        patterns = generate_pattern(parse_frags, args)
        pattern = patterns[0]
        print(f"   Сгенерирован паттерн: {pattern['type']} -> {pattern['selector']} (атрибут: {pattern['attribute']})")
        # Извлечение значения из первого фрагмента HTML
        html = html_list[0]
        extracted = extract_value(html, pattern, use_selenium=False)
        print(f"   Извлечённое значение: {extracted!r}")
        if label and extracted == label:
            print("   ⚠️  Извлечено label вместо value!")
        elif extracted == value:
            print("   ✅ Значение совпадает с ожидаемым.")
        else:
            print("   ❌ Значение не совпадает.")
    except Exception as e:
        print(f"   Ошибка: {e}")
        import traceback
        traceback.print_exc()

print("\n=== Тестирование завершено ===")