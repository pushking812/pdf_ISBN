import json

with open('isbn_data_cache.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

entries = data['entries']
rsl_entries = {k: v for k, v in entries.items() if v.get('source') == 'РГБ'}
print(f"Найдено записей РГБ: {len(rsl_entries)}")
for isbn, info in list(rsl_entries.items())[:5]:
    print(f"{isbn}: {info}")