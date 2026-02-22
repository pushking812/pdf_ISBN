import sys
import html_fragment

url = 'https://www.chitai-gorod.ru/product/python-dlya-neprogrammistov-samouchitel-v-primerah-3019372'
label = 'Тип обложки'
value = 'Мягкий переплёт'

print(f'Testing extract_common_parent_from_url with label={label!r}, value={value!r}', file=sys.stderr)

try:
    frags = html_fragment.extract_common_parent_from_url(
        url, label, value, 
        exact_label=True, 
        exact_value=True, 
        verbose=True, 
        search_mode='element'
    )
    print(f'Fragments found: {len(frags)}', file=sys.stderr)
    if frags:
        print(f'First fragment (first 500 chars):', file=sys.stderr)
        print(frags[0][:500], file=sys.stderr)
    else:
        print('No fragments', file=sys.stderr)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    import traceback
    traceback.print_exc()