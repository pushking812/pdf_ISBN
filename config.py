from typing import Tuple, List

class ScraperConfig:
    """Конфигурация скрапера."""
    def __init__(self,
                 headless: bool = False,
                 base_url: str = "https://www.chitai-gorod.ru",
                 skip_main_page: bool = False,
                 use_fast_selectors: bool = False,
                 # Фиксированные задержки
                 delay_after_main: Tuple[float, float] = (1.5, 2.5),
                 delay_after_search: Tuple[float, float] = (2.0, 3.0),
                 delay_after_click: Tuple[float, float] = (1.5, 2.5),
                 delay_between_actions: Tuple[float, float] = (0.3, 0.7),
                 wait_city_modal: int = 3,
                 wait_product_link: int = 6,
                 # Параметры асинхронного цикла
                 poll_interval: float = 0.5,
                 # Фразы, указывающие на отсутствие товара в результатах поиска
                 no_product_phrases: List[str] = None,
                 # Максимальное количество одновременно открытых вкладок
                 max_tabs: int = 5,
                 # Фразы, указывающие на блокировку (Too many requests)
                 rate_limit_phrases: List[str] = None,
                 # Начальная задержка при обнаружении блокировки (сек)
                 rate_limit_initial_delay: float = 10.0,
                 # Начальный коэффициент множителя
                 rate_limit_coef_start: float = 1.0,
                 # Шаг увеличения коэффициента
                 rate_limit_coef_step: float = 0.2,
                 # Максимальный коэффициент множителя
                 rate_limit_coef_max: float = 3.0,
                 # Обрабатывать ли блокировку (если False, то игнорируется)
                 handle_rate_limit: bool = True,
                 # Оставить браузер открытым после завершения (для отладки)
                 keep_browser_open: bool = False,
                 # Подробное логирование
                 verbose: bool = False,
                 # Макс. кол-во одновременно обрабатываемых ISBN на этапе API/РГБ (снижает блокировки РГБ/API)
                 api_max_concurrent: int = 5,
                 # Таймаут загрузки страницы (сек); при превышении — исключение
                 page_load_timeout: int = 20,
                 # Стратегия ожидания: "normal" (полная загрузка), "eager" (DOM готов), "none" (не ждать)
                 page_load_strategy: str = "eager",
                 # Пауза после открытия вкладки/загрузки URL (сек), вместо жёстких 0.5/0.2
                 delay_tab_switch: float = 0.2):
        self.headless = headless
        self.base_url = base_url
        self.skip_main_page = skip_main_page
        self.use_fast_selectors = use_fast_selectors
        self.delay_after_main = delay_after_main
        self.delay_after_search = delay_after_search
        self.delay_after_click = delay_after_click
        self.delay_between_actions = delay_between_actions
        self.wait_city_modal = wait_city_modal
        self.wait_product_link = wait_product_link
        self.poll_interval = poll_interval
        self.no_product_phrases = no_product_phrases or [
            "Похоже, у нас такого нет",
            "ничего не нашлось"
        ]
        self.max_tabs = max_tabs
        self.rate_limit_phrases = rate_limit_phrases or [
            "DDoS-Guard",
            "DDOS",
            "Checking your browser",
            "Доступ ограничен"
        ]
        self.rate_limit_initial_delay = rate_limit_initial_delay
        self.rate_limit_coef_start = rate_limit_coef_start
        self.rate_limit_coef_step = rate_limit_coef_step
        self.rate_limit_coef_max = rate_limit_coef_max
        self.handle_rate_limit = handle_rate_limit
        self.keep_browser_open = keep_browser_open
        self.verbose = verbose
        self.api_max_concurrent = api_max_concurrent
        self.page_load_timeout = page_load_timeout
        self.page_load_strategy = page_load_strategy
        self.delay_tab_switch = delay_tab_switch