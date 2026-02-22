import sys
sys.path.insert(0, '.')
import html_fragment

# Используем сохранённый HTML из файла, чтобы избежать сетевых запросов
with open('rsl_page.html', 'r', encoding='utf-8') as f:
    html = f.read()

label = ''
value = 'Мягкий переплёт'
print(f'Тест с пустым label, value={value!r}')
try:
    frags = html_fragment.extract_common_parent_html(
        html, label, value, 
        exact_label=True, 
        exact_value=True, 
        verbose=True, 
        search_mode='element',
        all_matches=False
    )
    print(f'   Найдено фрагментов: {len(frags)}')
    if frags:
        print(f'   Первый фрагмент (первые 500 символов):')
        print(frags[0][:500])
except Exception as e:
    print(f'   Ошибка: {e}')
    import traceback
    traceback.print_exc()