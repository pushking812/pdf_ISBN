#!/usr/bin/env python3
"""
Примеры использования новых компонентов оркестрационного слоя.

Этот файл содержит практические примеры использования компонентов,
реализованных в Итерациях A, B и C проекта.
"""

import asyncio
import logging

# Настройка логирования для примеров
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_search_coordinator():
    """
    Пример 1: Использование SearchCoordinator для оптимизации выбора ресурсов.
    
    SearchCoordinator анализирует статистику успешности ресурсов и выбирает
    наиболее подходящий ресурс для обработки конкретного ISBN.
    """
    print("\n=== Пример 1: SearchCoordinator ===")
    
    from scraper_core.orchestrator.search import SearchCoordinator
    
    # Создание координатора поиска
    coordinator = SearchCoordinator()
    
    # Имитация обновления статистики ресурсов
    coordinator.update_resource_stats("labirint", success=True, processing_time=2.5)
    coordinator.update_resource_stats("book24", success=False, processing_time=5.0)
    coordinator.update_resource_stats("chitai-gorod", success=True, processing_time=3.0)
    
    # Получение следующего ресурса для обработки ISBN
    isbn = "9785171204408"
    resource_id = await coordinator.get_next_resource(isbn)
    
    print(f"Для ISBN {isbn} выбран ресурс: {resource_id}")
    print("Приоритет ресурсов:")
    for resource in ["labirint", "book24", "chitai-gorod"]:
        priority = coordinator.get_resource_priority(resource)
        print(f"  - {resource}: {priority:.2f}")
    
    return coordinator


async def example_tab_manager():
    """
    Пример 2: Использование TabManager для управления вкладками браузера.
    
    TabManager обеспечивает эффективное управление вкладками браузера
    для параллельного скрапинга с балансировкой нагрузки.
    """
    print("\n=== Пример 2: TabManager ===")
    
    from scraper_core.orchestrator.tabs import TabManager
    
    # Создание менеджера вкладок (в примере используем моки)
    tab_manager = TabManager(max_tabs=3)
    
    # Имитация работы с вкладками
    resource_id = "labirint"
    
    print(f"Получение вкладки для ресурса {resource_id}...")
    # В реальном коде здесь будет получение реальной вкладки
    # tab = await tab_manager.acquire_tab(resource_id)
    
    print(f"Максимальное количество вкладок: {tab_manager.max_tabs}")
    print(f"Текущее количество активных вкладок: {tab_manager.active_tab_count}")
    
    # Освобождение вкладки
    # await tab_manager.release_tab(tab)
    
    print("TabManager готов к управлению параллельными запросами")
    return tab_manager


async def example_retry_handler():
    """
    Пример 3: Использование RetryHandler для обработки ошибок с экспоненциальным backoff.
    
    RetryHandler автоматически повторяет неудачные операции с увеличивающимися
    интервалами между попытками.
    """
    print("\n=== Пример 3: RetryHandler ===")
    
    from scraper_core.orchestrator.retry import RetryHandler
    
    # Создание обработчика повторных попыток
    retry_handler = RetryHandler(
        max_retries=3,
        backoff_factor=2.0,
        max_backoff_seconds=60
    )
    
    # Имитация функции, которая может завершиться с ошибкой
    attempt_count = 0
    
    async def unreliable_operation():
        nonlocal attempt_count
        attempt_count += 1
        
        if attempt_count < 3:
            raise ConnectionError(f"Сбой соединения (попытка {attempt_count})")
        return "Успешный результат"
    
    try:
        # Выполнение операции с повторными попытками
        result = await retry_handler.execute_with_retry(unreliable_operation)
        print(f"Результат: {result}")
        print(f"Потребовалось попыток: {attempt_count}")
    except Exception as e:
        print(f"Все попытки завершились ошибкой: {e}")
    
    return retry_handler


async def example_driver_manager():
    """
    Пример 4: Использование DriverManager для централизованного управления драйверами.
    
    DriverManager создает пул драйверов для переиспользования, что уменьшает
    накладные расходы на создание и уничтожение драйверов.
    """
    print("\n=== Пример 4: DriverManager ===")
    
    from scraper_core.orchestrator.drivers import SimpleDriverManager, DriverConfig
    
    # Конфигурация драйверов
    driver_config = DriverConfig(
        driver_type="selenium",
        headless=True,
        implicit_wait=10
    )
    
    # Создание менеджера драйверов
    driver_manager = SimpleDriverManager(
        config=driver_config,
        max_drivers=2
    )
    
    print(f"Тип драйвера: {driver_manager.config.driver_type}")
    print(f"Headless режим: {driver_manager.config.headless}")
    print(f"Максимальное количество драйверов: {driver_manager.max_drivers}")
    
    # В реальном коде:
    # driver = await driver_manager.get_driver("labirint")
    # ... использование драйвера ...
    # await driver_manager.release_driver(driver)
    
    print("DriverManager готов к управлению драйверами")
    return driver_manager


async def example_antibot_handler():
    """
    Пример 5: Использование AntiBotHandler для обхода блокировок.
    
    AntiBotHandler применяет стратегии для обнаружения и обхода
    анти-бот защиты на целевых сайтах.
    """
    print("\n=== Пример 5: AntiBotHandler ===")
    
    from scraper_core.orchestrator.antibot import SimpleAntiBotHandler, AntiBotConfig
    
    # Конфигурация анти-бот защиты
    antibot_config = AntiBotConfig(
        enable_proxy_rotation=False,
        user_agents=[
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        ],
        random_delay_range=(1, 3)
    )
    
    # Создание обработчика анти-бот защиты
    antibot_handler = SimpleAntiBotHandler(config=antibot_config)
    
    print(f"Ротация User-Agent: {'Включена' if antibot_handler.config.enable_user_agent_rotation else 'Выключена'}")
    print(f"Количество User-Agent: {len(antibot_handler.config.user_agents)}")
    print(f"Случайная задержка: {antibot_handler.config.random_delay_range} секунд")
    
    # Имитация обнаружения блокировки
    mock_response = type('MockResponse', (), {'text': 'Доступ заблокирован'})()
    is_blocked = antibot_handler.detect_blocking(mock_response)
    
    print(f"Обнаружена блокировка: {is_blocked}")
    
    return antibot_handler


async def example_link_collector():
    """
    Пример 6: Использование LinkCollector для сбора и валидации ссылок.
    
    LinkCollector извлекает ссылки из HTML-контента, фильтрует дубликаты
    и валидирует URL.
    """
    print("\n=== Пример 6: LinkCollector ===")
    
    from scraper_core.orchestrator.links import LinkCollector
    
    # Создание коллектора ссылок
    link_collector = LinkCollector()
    
    # Пример HTML-контента
    html_content = """
    <html>
        <body>
            <a href="https://www.labirint.ru/books/123">Книга 1</a>
            <a href="/books/456">Книга 2 (относительная ссылка)</a>
            <a href="https://www.book24.ru/product/789">Книга 3</a>
            <a href="invalid-url">Невалидная ссылка</a>
            <a href="https://www.labirint.ru/books/123">Дубликат книги 1</a>
        </body>
    </html>
    """
    
    base_url = "https://www.labirint.ru"
    
    # Сбор ссылок
    links = await link_collector.collect_links(html_content, base_url)
    
    print(f"Найдено ссылок: {len(links)}")
    print("Собранные ссылки:")
    for link in links:
        print(f"  - {link}")
    
    # Фильтрация ссылок по паттерну
    labirint_links = link_collector.filter_links(links, ["labirint.ru"])
    print(f"\nСсылки на labirint.ru: {len(labirint_links)}")
    
    # Валидация URL
    test_urls = [
        "https://www.labirint.ru/books/123",
        "invalid-url",
        "http://example.com",
        "ftp://server.com/file"
    ]
    
    print("\nВалидация URL:")
    for url in test_urls:
        is_valid = link_collector.validate_url(url)
        print(f"  - {url}: {'✓ Валиден' if is_valid else '✗ Невалиден'}")
    
    return link_collector


async def example_full_orchestrator():
    """
    Пример 7: Полное использование ScraperOrchestrator со всеми компонентами.
    
    ScraperOrchestrator интегрирует все компоненты оркестрационного слоя
    для выполнения комплексных задач скрапинга.
    """
    print("\n=== Пример 7: Полный ScraperOrchestrator ===")
    
    from scraper_core.orchestrator.core import ScraperOrchestrator
    from scraper_core.orchestrator.retry import RetryConfig
    from scraper_core.orchestrator.drivers import DriverConfig
    from scraper_core.orchestrator.antibot import AntiBotConfig
    
    # Расширенная конфигурация компонентов
    retry_config = RetryConfig(
        max_retries=3,
        backoff_factor=2.0,
        retryable_errors=["TimeoutError", "ConnectionError"]
    )
    
    driver_config = DriverConfig(
        driver_type="selenium",
        headless=True,
        implicit_wait=10
    )
    
    antibot_config = AntiBotConfig(
        enable_proxy_rotation=False,
        random_delay_range=(1, 3)
    )
    
    # Создание оркестратора с расширенными настройками
    orchestrator = ScraperOrchestrator(
        config_dir="config",
        max_concurrent_tasks=3,
        use_search_coordinator=True,
        use_tab_manager=True,
        use_retry_handler=True,
        use_driver_manager=True,
        use_antibot_handler=True,
        use_priority_queue=True,
        retry_config=retry_config,
        driver_config=driver_config,
        antibot_config=antibot_config,
        max_tabs=2
    )
    
    print("Конфигурация оркестратора:")
    print(f"  - Максимальное количество задач: {orchestrator.max_concurrent_tasks}")
    print(f"  - Использование SearchCoordinator: {orchestrator.use_search_coordinator}")
    print(f"  - Использование TabManager: {orchestrator.use_tab_manager}")
    print(f"  - Использование RetryHandler: {orchestrator.use_retry_handler}")
    print(f"  - Использование DriverManager: {orchestrator.use_driver_manager}")
    print(f"  - Использование AntiBotHandler: {orchestrator.use_antibot_handler}")
    print(f"  - Использование приоритетной очереди: {orchestrator.use_priority_queue}")
    print(f"  - Максимальное количество вкладок: {orchestrator.max_tabs}")
    
    # В реальном коде:
    # isbns = ["9785171204408", "9785171204415", "9785171204422"]
    # results = await orchestrator.scrape_isbns(isbns)
    
    print("\nОркестратор готов к работе со всеми компонентами")
    return orchestrator


async def example_legacy_adapter():
    """
    Пример 8: Использование LegacyAdapter для обратной совместимости.
    
    LegacyAdapter обеспечивает совместимость нового оркестрационного слоя
    со старым кодом, использующим функции из scraper.py.
    """
    print("\n=== Пример 8: LegacyAdapter для обратной совместимости ===")
    
    from scraper_core.orchestrator.legacy_adapter import LegacyScraperAdapter
    
    # Создание адаптера
    adapter = LegacyScraperAdapter()
    
    print("LegacyAdapter предоставляет совместимость со старым API:")
    print("  - async_parallel_search() - асинхронный параллельный поиск")
    print("  - search_multiple_books() - синхронный поиск нескольких книг")
    print("  - parse_book_page_for_resource() - парсинг страниц по ресурсам")
    
    # В реальном коде:
    # results = await adapter.async_parallel_search(["9785171204408"])
    # print(f"Результаты: {results}")
    
    print("\nАдаптер готов к использованию старого API с новой архитектурой")
    return adapter


async def example_dual_write_cache():
    """
    Пример 9: Использование DualWriteCacheManager для миграции данных.
    
    DualWriteCacheManager обеспечивает одновременную запись в старые и новые
    кэши, что позволяет плавно мигрировать на новую архитектуру.
    """
    print("\n=== Пример 9: DualWriteCacheManager для миграции данных ===")
    
    from scraper_core.integration.dual_write import DualWriteCacheManager
    
    # Создание менеджера dual-write кэшей
    cache_manager = DualWriteCacheManager(
        old_isbn_cache_path="isbn_data_cache.json",
        old_pdf_cache_path="pdf_isbn_cache.json",
        new_cache_dir="cache/new"
    )
    
    print("DualWriteCacheManager обеспечивает:")
    print("  - Одновременную запись в старые и новые кэши")
    print("  - Чтение данных с приоритетом нового кэша")
    print("  - Миграцию данных из старых кэшей в новые")
    
    # Пример данных для записи
    example_data = {
        "9785171204408": {
            "title": "Пример книги",
            "author": "Пример автора",
            "year": 2023,
            "resource": "labirint"
        }
    }
    
    # В реальном коде:
    # await cache_manager.write_isbn_data("9785171204408", example_data["9785171204408"])
    # data = await cache_manager.read_isbn_data("9785171204408")
    # print(f"Прочитанные данные: {data}")
    
    print("\nDualWriteCacheManager готов к миграции данных")
    return cache_manager


async def main():
    """
    Основная функция для запуска всех примеров.
    """
    print("=" * 60)
    print("Примеры использования новых компонентов оркестрационного слоя")
    print("=" * 60)
    
    try:
        # Запуск всех примеров
        await example_search_coordinator()
        await example_tab_manager()
        await example_retry_handler()
        await example_driver_manager()
        await example_antibot_handler()
        await example_link_collector()
        await example_full_orchestrator()
        await example_legacy_adapter()
        await example_dual_write_cache()
        
        print("\n" + "=" * 60)
        print("Все примеры успешно выполнены!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nОшибка при выполнении примеров: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Запуск асинхронной основной функции
    asyncio.run(main())