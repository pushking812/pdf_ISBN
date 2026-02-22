from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

options = Options()
options.add_argument("--headless")  # Фоновый режим
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)

try:
    driver.get("https://search.rsl.ru/ru/search#q=9785977520966")
    # Ждём появления результатов
    wait = WebDriverWait(driver, 10)
    # Попробуем дождаться любого контейнера с результатами
    wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".search-results, .search-container, .item")
        )
    )
    time.sleep(2)  # Дополнительная задержка для полной загрузки

    # Выведем весь HTML страницы
    html = driver.page_source
    with open("rsl_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML сохранён в rsl_page.html")

    # Поиск контейнеров
    containers = driver.find_elements(By.CSS_SELECTOR, "div.search-container")
    print(f"Найдено контейнеров search-container: {len(containers)}")
    for i, container in enumerate(containers[:3]):
        print(f"Контейнер {i}:")
        print(container.get_attribute("outerHTML")[:500])
        print("---")

    # Поиск автора
    authors = driver.find_elements(By.CSS_SELECTOR, "b.js-item-authorinfo")
    print(f"Найдено авторов js-item-authorinfo: {len(authors)}")
    for a in authors:
        print(f"Автор: {a.text}")

    # Поиск описания
    descs = driver.find_elements(By.CSS_SELECTOR, "span.js-item-maininfo")
    print(f"Найдено описаний js-item-maininfo: {len(descs)}")
    for d in descs:
        print(f"Описание: {d.text}")

    # Если не нашли, попробуем другие селекторы
    if len(containers) == 0:
        print("Ищем другие возможные селекторы...")
        all_divs = driver.find_elements(By.CSS_SELECTOR, "div")
        for div in all_divs[:20]:
            cls = div.get_attribute("class")
            if cls and "search" in cls:
                print(f"Класс div: {cls}")

finally:
    driver.quit()
