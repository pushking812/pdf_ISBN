import re

description = "Программирование микроконтроллеров на Python : практическое руководство : учебник и задачник / Дэн Айзел. - Москва-Санкт-Петербург : Питер-Пресс, 2025 (Москва, Московская типография). - 288 с.; 21 см.; ISBN 978-5-9775-2096-6 : 1000 экз."

# Регулярные выражения из api_clients.py
year_match = re.search(r',\s*(\d{4})\.', description)
if year_match:
    year = year_match.group(1)
    print(f"Год найден: {year}")
else:
    print("Год не найден")

pages_match = re.search(r'\.\s*-\s*(\d+)\s+с\.', description)
if pages_match:
    pages = pages_match.group(1)
    print(f"Страницы найдены: {pages}")
else:
    print("Страницы не найдены")

# Также проверим извлечение названия
title = description.split(' / ')[0].strip()
print(f"Название: {title}")

# Проверим автора (из другого источника)
author = "Дэн Айзел"
print(f"Автор: {author}")