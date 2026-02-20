# План замены заглушек в api_clients.py

## Цель
Заменить заглушки в файле `api_clients.py` реализацией на основе модуля `scrapper16.py`, создав асинхронные версии функций с использованием `aiohttp` для лучшей производительности.

## Текущее состояние
- `api_clients.py` содержит заглушки для синхронных и асинхронных функций Google Books, Open Library, РГБ.
- `scrapper16.py` содержит реализацию синхронных функций `get_from_google_books`, `get_from_open_library`, `get_from_rsl`.
- В проекте уже есть `utils.py` с функцией `normalize_isbn`.

## План изменений

### 1. Обновление импортов в `api_clients.py`
Добавить необходимые импорты из `scrapper16.py` и `utils.py`:
```python
import aiohttp
import re
from typing import Any, Optional, Dict, List
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from utils import normalize_isbn
```

### 2. Синхронные функции (копирование из scrapper16.py)
Заменить существующие заглушки на реализацию из `scrapper16.py` с небольшими улучшениями:
- Использовать `normalize_isbn` из `utils.py`
- Добавить обработку ошибок
- Сохранить сигнатуры функций

### 3. Асинхронные функции (новые реализации)
Создать асинхронные версии с использованием `aiohttp`:
- `get_from_google_books_async`
- `get_from_open_library_async`
- `get_from_rsl_async`

Каждая функция должна:
- Принимать `aiohttp.ClientSession` и `isbn`
- Выполнять HTTP-запросы асинхронно
- Парсить ответ аналогично синхронным версиям
- Возвращать `Dict` с данными книги или `None`

### 4. Детали реализации

#### Google Books API
- URL: `https://www.googleapis.com/books/v1/volumes`
- Параметры: `q=f"isbn:{isbn}"`, `maxResults=1`
- Извлечение: title, authors, pageCount, publishedDate

#### Open Library API
- URL: `https://openlibrary.org/api/books`
- Параметры: `bibkeys=f"ISBN:{isbn}"`, `format=json`, `jscmd=data`
- Извлечение: title, authors, number_of_pages, publish_date

#### РГБ (Российская государственная библиотека)
- URL: `https://search.rsl.ru/ru/search`
- Параметры: `q=isbn`
- Парсинг HTML: поиск по классам `search-container`, `js-item-authorinfo`, `js-item-maininfo`
- Извлечение: title, authors, pages, year

### 5. Проверка изменений
- Запустить `ruff check .` для проверки синтаксиса
- Проверить импорты на корректность
- Убедиться, что существующий код (scraper.py) продолжает работать

## Шаги реализации

1. **Создать резервную копию** текущего `api_clients.py`
2. **Написать новый код** в отдельном файле для проверки
3. **Заменить содержимое** `api_clients.py` новым кодом
4. **Проверить синтаксис** с помощью `python -m py_compile api_clients.py`
5. **Протестировать** функции на примере ISBN (например, "978-5-4461-1234-8")
6. **Интеграционное тестирование** с `scraper.py` и `main.py`

## Риски и решения
- **Риск**: Изменение сигнатур функций может сломать существующий код.
  **Решение**: Сохранить точно такие же сигнатуры, как в заглушках.
- **Риск**: Асинхронные функции могут работать медленнее из-за ошибок реализации.
  **Решение**: Использовать пул соединений aiohttp и таймауты.
- **Риск**: РГБ может блокировать запросы при частом обращении.
  **Решение**: Добавить задержки и обработку ошибок 429.

## Зависимости
Убедиться, что установлены пакеты:
- `aiohttp`
- `requests`
- `beautifulsoup4`
- `isbnlib`
- `lxml`

## Время реализации
Ориентировочно 1-2 часа на написание и тестирование кода.

## Утверждение плана
После утверждения плана можно переходить к реализации в режиме Code.