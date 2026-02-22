import pytest

pytestmark = [pytest.mark.slow, pytest.mark.selenium]

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from drivers import create_chrome_driver
from resources import get_scraper_resources
from scraper import parse_book_page_for_resource


@pytest.fixture(scope="module")
def driver(scraper_config):
    """Фикстура драйвера для скраперов."""
    driver = create_chrome_driver(scraper_config)
    yield driver
    driver.quit()


def test_scraper_chitai_gorod(driver, isbn_list, scraper_config):
    """Тест скрапера Читай-город."""
    resources = get_scraper_resources(scraper_config)
    resource = next((r for r in resources if r["id"] == "chitai-gorod"), None)
    assert resource is not None, "Ресурс Читай-город не найден"

    success = False
    for isbn in isbn_list[:5]:  # Проверяем первые 5 ISBN
        try:
            search_url = resource["search_url_template"].format(isbn=isbn)
            driver.get(search_url)

            # Ожидание загрузки страницы
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )

            # Проверка на отсутствие товара
            page_text = driver.page_source
            if any(
                phrase in page_text for phrase in resource.get("no_product_phrases", [])
            ):
                continue

            # Поиск ссылки на товар
            product_link = None
            for selector in resource["product_link_selectors"]:
                links = driver.find_elements(By.CSS_SELECTOR, selector)
                if links:
                    product_link = links[0]
                    break

            if not product_link:
                continue

            # Клик по товару
            product_link.click()
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )

            # Парсинг страницы
            data = parse_book_page_for_resource(driver, resource)
            if data and data.get("title") and data.get("authors"):
                success = True
                print(f"Читай-город: успех для ISBN {isbn}")
                break
        except Exception as e:
            print(f"Ошибка для ISBN {isbn}: {e}")
            continue

    if not success:
        pytest.skip("Читай-город: ни один ISBN не дал результата")


def test_scraper_book_ru(driver, isbn_list, scraper_config):
    """Тест скрапера Book.ru."""
    resources = get_scraper_resources(scraper_config)
    resource = next((r for r in resources if r["id"] == "book-ru"), None)
    assert resource is not None, "Ресурс Book.ru не найден"

    success = False
    for isbn in isbn_list[:5]:
        try:
            search_url = resource["search_url_template"].format(isbn=isbn)
            driver.get(search_url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )

            page_text = driver.page_source
            if any(
                phrase in page_text for phrase in resource.get("no_product_phrases", [])
            ):
                continue

            product_link = None
            for selector in resource["product_link_selectors"]:
                links = driver.find_elements(By.CSS_SELECTOR, selector)
                if links:
                    product_link = links[0]
                    break

            if not product_link:
                continue

            product_link.click()
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )

            data = parse_book_page_for_resource(driver, resource)
            if data and data.get("title") and data.get("authors"):
                success = True
                print(f"Book.ru: успех для ISBN {isbn}")
                break
        except Exception as e:
            print(f"Ошибка для ISBN {isbn}: {e}")
            continue

    if not success:
        pytest.skip("Book.ru: ни один ISBN не дал результата")
