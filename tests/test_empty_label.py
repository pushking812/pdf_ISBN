import sys
sys.path.insert(0, '.')
import html_fragment

# Тест 1: пустой label, непустое значение
url = 'https://www.chitai-gorod.ru/product/python-dlya-neprogrammistov-samouchitel-v-primerah-3019372'
label = ''
value = 'Мягкий переплёт'
print(f'Тест 1: label={label!r}, value={value!r}')
try:
    frags = html_fragment.extract_common_parent_from_url(
        url, label, value, 
        exact_label=True, 
        exact_value=True, 
        verbose=True, 
        search_mode='element'
    )
    print(f'   Найдено фрагментов: {len(frags)}')
except Exception as e:
    print(f'   Ошибка: {e}')

# Тест 2: label='<Отсутствует>', value='<Отсутствует>'
label2 = '<Отсутствует>'
value2 = '<Отсутствует>'
print(f'\nТест 2: label={label2!r}, value={value2!r}')
try:
    frags2 = html_fragment.extract_common_parent_from_url(
        url, label2, value2, 
        exact_label=True, 
        exact_value=True, 
        verbose=True, 
        search_mode='element'
    )
    print(f'   Найдено фрагментов: {len(frags2)}')
except Exception as e:
    print(f'   Ошибка: {e}')

# Тест 3: label=None? функция ожидает строку, передадим None
label3 = None
value3 = 'Мягкий переплёт'
print(f'\nТест 3: label={label3!r}, value={value3!r}')
try:
    frags3 = html_fragment.extract_common_parent_from_url(
        url, label3, value3, 
        exact_label=True, 
        exact_value=True, 
        verbose=True, 
        search_mode='element'
    )
    print(f'   Найдено фрагментов: {len(frags3)}')
except Exception as e:
    print(f'   Ошибка: {e}')

# Тест 4: поиск только значения (label='', exact_label=False)
print(f'\nТест 4: label пустой, exact_label=False')
try:
    frags4 = html_fragment.extract_common_parent_from_url(
        url, '', value, 
        exact_label=False, 
        exact_value=True, 
        verbose=True, 
        search_mode='element'
    )
    print(f'   Найдено фрагментов: {len(frags4)}')
except Exception as e:
    print(f'   Ошибка: {e}')