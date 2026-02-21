# Интеграция с pytest и настройка зависимостей

## Цель
Обеспечить корректную работу тестов с pytest, установить необходимые зависимости и настроить окружение.

## Шаги

### 1. Проверка установленных зависимостей
Проверить, какие пакеты уже установлены в проекте. Можно создать файл `requirements.txt` или `pyproject.toml` для управления зависимостями.

### 2. Установка недостающих пакетов
Для работы тестов потребуются:
- pytest
- pytest-asyncio (для асинхронных тестов)
- requests (уже используется)
- aiohttp (уже используется)
- beautifulsoup4 (уже используется)
- selenium (уже используется)
- webdriver-manager (для автоматического управления драйверами)

Команда установки:
```bash
pip install pytest pytest-asyncio webdriver-manager
```

### 3. Создание файла конфигурации pytest
Создать `pyproject.toml` или `pytest.ini` для настройки pytest.

Пример `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
asyncio_mode = "auto"
```

### 4. Настройка фикстур
Убедиться, что фикстуры в `conftest.py` корректно работают:
- `isbn_list` загружает ISBN из файла.
- `aiohttp_session` создаёт и закрывает сессию.
- `scraper_config` создаёт конфиг с headless=True для тестов.
- `driver` создаёт и закрывает браузер.

### 5. Обработка ошибок и таймауты
- Увеличить таймауты для сетевых запросов (особенно для РГБ и скраперов).
- Добавить повторные попытки (retry) для неустойчивых ресурсов.
- Пропускать тесты, если ресурс временно недоступен (использовать `pytest.skip`).

### 6. Запуск тестов в CI
Предложить конфигурацию для GitHub Actions или другого CI.

Пример `.github/workflows/test.yml`:
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio webdriver-manager
      - name: Run tests
        run: pytest tests/ -v
```

### 7. Проверка покрытия (опционально)
Установить `pytest-cov` для измерения покрытия кода:
```bash
pip install pytest-cov
pytest tests/ --cov=.
```

### 8. Документация
Добавить в README инструкцию по запуску тестов.

## Потенциальные проблемы и решения

### Проблема 1: Отсутствие ChromeDriver
Решение: использовать `webdriver-manager` для автоматической загрузки драйвера.

В `drivers.py` добавить:
```python
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def create_chrome_driver(headless=False):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver
```

### Проблема 2: Блокировка ресурсов (rate limiting)
Решение: добавить задержки между запросами и использовать разные ISBN.

### Проблема 3: Асинхронные тесты падают с ошибками цикла событий
Решение: убедиться, что используется `pytest.mark.asyncio` и `asyncio_mode = "auto"` в конфиге.

### Проблема 4: Тесты скраперов требуют графической среды
Решение: запускать в headless-режиме (уже настроено).

## Следующие действия
1. Создать `requirements.txt` с актуальными зависимостями.
2. Настроить `pyproject.toml`.
3. Реализовать фикстуры в `conftest.py`.
4. Запустить тесты и исправить ошибки.
5. Добавить CI конфигурацию (опционально).