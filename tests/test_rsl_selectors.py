import requests
from bs4 import BeautifulSoup
import re

def test_rsl_selectors(isbn="9785977520966"):
    url = "https://search.rsl.ru/ru/search"
    params = {"q": isbn}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        print("HTML загружен, размер:", len(response.text), "символов")
        
        # Проверка контейнеров
        containers = soup.find_all('div', class_='search-container')
        print(f"Найдено контейнеров search-container: {len(containers)}")
        if containers:
            first = containers[0]
            print("Первый контейнер HTML:", first.prettify()[:500])
            
            # Автор
            author_tag = first.find('b', class_='js-item-authorinfo')
            print(f"Тег автора (b.js-item-authorinfo): {author_tag}")
            if author_tag:
                print(f"Текст автора: {author_tag.text.strip()}")
            
            # Основная информация
            desc_span = first.find('span', class_='js-item-maininfo')
            print(f"Тег описания (span.js-item-maininfo): {desc_span}")
            if desc_span:
                description = desc_span.text.strip()
                print(f"Описание: {description}")
                
                # Извлечение названия
                title = description.split(' / ')[0].strip()
                print(f"Извлечённое название: {title}")
                
                # Год
                year_match = re.search(r',\s*(\d{4})\.', description)
                if year_match:
                    print(f"Год: {year_match.group(1)}")
                else:
                    print("Год не найден")
                
                # Страницы
                pages_match = re.search(r'\.\s*-\s*(\d+)\s+с\.', description)
                if pages_match:
                    print(f"Страницы: {pages_match.group(1)}")
                else:
                    print("Страницы не найдены")
            else:
                print("ОШИБКА: span.js-item-maininfo не найден")
        else:
            print("ОШИБКА: контейнеры search-container не найдены")
            # Выведем часть HTML для отладки
            print("Первые 2000 символов HTML:")
            print(response.text[:2000])
    except Exception as e:
        print(f"Ошибка при запросе: {e}")

if __name__ == "__main__":
    test_rsl_selectors()