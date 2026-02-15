from typing import Any
import undetected_chromedriver as uc
from config import ScraperConfig

def create_chrome_driver(config: ScraperConfig) -> Any:
    """
    Создаёт Chrome с таймаутами и стратегией загрузки из конфига.
    Ускоряет работу: не ждём полной загрузки страницы (eager), ограничиваем таймаут.
    """
    strategy = (getattr(config, 'page_load_strategy', None) or "eager").strip().lower()
    if strategy not in ("normal", "eager", "none"):
        strategy = "eager"
    options = uc.ChromeOptions()
    options.set_capability("pageLoadStrategy", strategy)
    driver = uc.Chrome(headless=config.headless, options=options)
    driver.set_window_size(1920, 1080)
    timeout_sec = max(5, getattr(config, 'page_load_timeout', 20))
    driver.set_page_load_timeout(timeout_sec)
    driver.set_script_timeout(timeout_sec)
    driver.implicitly_wait(0)  # только явные WebDriverWait, без лишнего ожидания
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver