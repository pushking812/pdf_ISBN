#!/usr/bin/env python3
"""
Главный модуль для извлечения ISBN из PDF-файлов и поиска информации о книгах.
Использует:
- pdf_extract_isbn.py для извлечения ISBN из PDF
- web_scraper_isbn.py для поиска данных по ISBN (API и скрапинг)

Конфигурация задаётся через JSON-файл (параметр --config) или через аргументы командной строки
(только основные: директория, headless, verbose, output). Для тонкой настройки используйте JSON.
"""

import asyncio
import argparse
import json
import logging
import sys
import time
import random
from typing import Dict, List, Optional, Tuple, Any, Callable
from collections import defaultdict
from functools import partial
import os

# Импорт из предоставленных модулей
from pdf_extract_isbn import scan_pdfs, logger as pdf_logger
from web_scraper_isbn import (
    search_multiple_books,
    ScraperConfig,
    normalize_isbn,
    run_api_stage,
    RussianBookScraperUC,
    TabState,
    TabInfo,
    TimeoutException,
    NoSuchElementException,
    By,
    WebDriverWait,
    EC,
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def truncate_path(path: str, max_len: int = 60) -> str:
    """Обрезает путь, сохраняя конец, если он слишком длинный."""
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3):]


def load_config_from_json(json_path: str) -> dict:
    """Загружает конфигурацию из JSON-файла."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def merge_config(base_config: dict, cli_args: dict) -> dict:
    """
    Объединяет конфигурацию из JSON и аргументов командной строки.
    Аргументы CLI имеют приоритет.
    """
    merged = base_config.copy()
    for key, value in cli_args.items():
        if value is not None:  # только если аргумент явно задан
            merged[key] = value
    return merged


# ========== ФУНКЦИИ ДЛЯ ЭТАПА СКРАПИНГА С ТАБЛИЧНЫМ ПРОГРЕССОМ ==========

def parallel_search_with_progress(
    isbn_list: List[str],
    config: ScraperConfig,
    progress_callback: Callable[[int, Optional[Dict[str, Any]]], None]
) -> List[Optional[Dict[str, Any]]]:
    """
    Аналог async_parallel_search из web_scraper_isbn, но с вызовом callback
    для каждого обработанного ISBN (по мере готовности).
    progress_callback(index, result) вызывается, когда для ISBN с данным индексом
    получен результат (или None, если не найден).
    """
    # Импортируем undetected_chromedriver здесь, чтобы избежать лишних зависимостей в основном модуле
    import undetected_chromedriver as uc

    # Создаём драйвер (вне контекстного менеджера, чтобы управлять вручную)
    driver = uc.Chrome(headless=config.headless)
    driver.set_window_size(1920, 1080)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Обработка главной страницы, если нужно
    if not config.skip_main_page:
        driver.get(config.base_url)
        time.sleep(random.uniform(*config.delay_after_main))
        try:
            WebDriverWait(driver, config.wait_city_modal).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Да, я здесь')]"))
            ).click()
            if config.verbose:
                logger.debug("Город подтверждён (главное окно)")
            time.sleep(random.uniform(*config.delay_between_actions))
        except:
            pass
    else:
        if config.verbose:
            logger.debug("Пропускаем главную страницу")

    # Разбиваем список ISBN на чанки по max_tabs
    chunks = [isbn_list[i:i + config.max_tabs] for i in range(0, len(isbn_list), config.max_tabs)]
    all_results = [None] * len(isbn_list)
    rate_limit_attempts = 0

    # Создаём временный объект scraper для доступа к селекторам
    scraper_template = RussianBookScraperUC(config)

    for chunk_idx, chunk in enumerate(chunks):
        if config.verbose:
            logger.debug(f"Обработка чанка {chunk_idx + 1}/{len(chunks)} (ISBN: {chunk})")

        # Создание вкладок для текущего чанка
        handles = []
        try:
            main_handle = driver.current_window_handle
            handles.append(main_handle)
            for i in range(1, len(chunk)):
                driver.switch_to.new_window('tab')
                time.sleep(0.5)
                new_handle = driver.current_window_handle
                if new_handle not in handles:
                    handles.append(new_handle)
                else:
                    all_handles = driver.window_handles
                    found = False
                    for h in all_handles:
                        if h not in handles:
                            handles.append(h)
                            found = True
                            break
                    if not found:
                        raise Exception(f"Не удалось получить новый handle для вкладки {i}")
        except Exception as e:
            logger.error(f"Ошибка создания вкладок для чанка {chunk_idx}: {e}")
            # Помечаем все ISBN чанка как необработанные
            for j, _ in enumerate(chunk):
                idx = chunk_idx * config.max_tabs + j
                all_results[idx] = None
                progress_callback(idx, None)
            time.sleep(1)
            continue

        # Создаём объекты TabInfo с правильными индексами
        tabs = []
        for i, isbn in enumerate(chunk):
            global_idx = chunk_idx * config.max_tabs + i
            tabs.append(TabInfo(isbn, handles[i], global_idx, config))

        # Загрузка поисковых страниц в каждую вкладку
        for tab in tabs:
            try:
                driver.switch_to.window(tab.handle)
                clean_isbn = tab.isbn.replace("-", "").strip()
                search_url = f"{config.base_url}/search?phrase={clean_isbn}"
                driver.get(search_url)
                tab.state = TabState.SEARCHING
                tab.search_start_time = time.time()
                time.sleep(0.2)
            except Exception as e:
                logger.error(f"[Вкладка {tab.index}] Не удалось загрузить поиск: {e}")
                tab.state = TabState.ERROR
                progress_callback(tab.index, None)

        # Основной цикл обработки чанка
        all_done = False
        while not all_done:
            all_done = True
            for tab in tabs:
                if tab.state in (TabState.DONE, TabState.ERROR, TabState.RATE_LIMITED):
                    continue
                all_done = False

                try:
                    driver.switch_to.window(tab.handle)
                except Exception as e:
                    logger.error(f"[Вкладка {tab.index}] Ошибка переключения: {e}")
                    tab.state = TabState.ERROR
                    progress_callback(tab.index, None)
                    continue

                # Проверка блокировки
                if config.handle_rate_limit:
                    try:
                        page_source = driver.page_source
                        found_rate_limit = any(phrase.lower() in page_source.lower() for phrase in config.rate_limit_phrases)
                        if found_rate_limit:
                            logger.warning(f"[Вкладка {tab.index}] Обнаружена блокировка")
                            rate_limit_attempts += 1
                            coef = config.rate_limit_coef_start + (rate_limit_attempts - 1) * config.rate_limit_coef_step
                            coef = min(coef, config.rate_limit_coef_max)
                            wait_time = config.rate_limit_initial_delay * coef
                            logger.info(f"Пауза {wait_time:.1f}с (коэф. {coef:.2f})")
                            time.sleep(wait_time)
                            driver.refresh()
                            while True:
                                time.sleep(config.poll_interval)
                                page_source = driver.page_source
                                if any(phrase.lower() in page_source.lower() for phrase in config.rate_limit_phrases):
                                    time.sleep(wait_time)
                                    driver.refresh()
                                else:
                                    logger.debug("Блокировка снята, сброс счётчика")
                                    rate_limit_attempts = 0
                                    break
                            for t in tabs:
                                if t.handle != tab.handle:
                                    try:
                                        driver.switch_to.window(t.handle)
                                        driver.refresh()
                                        time.sleep(0.5)
                                    except:
                                        pass
                            driver.switch_to.window(tab.handle)
                            break
                        else:
                            if rate_limit_attempts > 0:
                                rate_limit_attempts = 0
                    except Exception:
                        pass

                if tab.state == TabState.SEARCHING:
                    try:
                        page_source = driver.page_source
                        if any(phrase in page_source for phrase in config.no_product_phrases):
                            logger.debug(f"[Вкладка {tab.index}] Товар не найден")
                            tab.state = TabState.ERROR
                            progress_callback(tab.index, None)
                            continue
                    except:
                        pass

                    elapsed = time.time() - tab.search_start_time
                    found_link = None
                    for selector in scraper_template.product_link_selectors:
                        try:
                            element = driver.find_element(By.CSS_SELECTOR, selector)
                            found_link = element
                            break
                        except NoSuchElementException:
                            continue
                    if found_link:
                        tab.book_url = found_link.get_attribute('href')
                        driver.get(tab.book_url)
                        time.sleep(random.uniform(*config.delay_after_click))
                        tab.state = TabState.BOOK_PAGE
                        logger.debug(f"[Вкладка {tab.index}] Перешли на страницу книги")
                    else:
                        if elapsed > tab.timeout:
                            logger.debug(f"[Вкладка {tab.index}] Превышен таймаут")
                            tab.state = TabState.ERROR
                            progress_callback(tab.index, None)

                elif tab.state == TabState.BOOK_PAGE:
                    try:
                        scraper_template.driver = driver
                        result = scraper_template._parse_book_page()
                        tab.result = result
                        tab.state = TabState.DONE
                        rate_limit_attempts = 0
                        all_results[tab.index] = result
                        progress_callback(tab.index, result)
                        logger.debug(f"[Вкладка {tab.index}] ISBN {tab.isbn} готов")
                    except Exception as e:
                        logger.error(f"[Вкладка {tab.index}] Ошибка парсинга: {e}")
                        tab.state = TabState.ERROR
                        progress_callback(tab.index, None)

            if not all_done:
                time.sleep(config.poll_interval)

        # Закрытие вкладок чанка (кроме главной)
        main_handle = handles[0]
        for handle in handles[1:]:
            try:
                driver.switch_to.window(handle)
                driver.close()
            except:
                pass
        driver.switch_to.window(main_handle)
        time.sleep(1)

    if not config.keep_browser_open:
        driver.quit()
    else:
        input("\n🔍 Браузер оставлен открытым. Нажмите Enter для закрытия...")
        driver.quit()

    return all_results


async def run_scraping_stage(
    isbn_list: List[str],
    indices: List[int],  # не используется, оставлено для совместимости
    config: ScraperConfig
) -> List[Optional[Dict[str, Any]]]:
    """
    Запускает скрапинг Читай-города для списка ISBN с выводом прогресса в таблицу.
    Возвращает список результатов (размер равен len(isbn_list)) в порядке isbn_list.
    """
    if not isbn_list:
        return []

    print(f"\n🔍 Скрапинг Читай-город для {len(isbn_list)} ISBN (параллельно):")
    header = f"{' №':>4} | {'ISBN':<20} | {'Статус':<25} | {'Название'}"
    print(header)
    print("-" * len(header))

    results = [None] * len(isbn_list)

    def progress_callback(idx: int, res: Optional[Dict[str, Any]]):
        # idx - локальный индекс в isbn_list (0..len(isbn_list)-1)
        isbn = isbn_list[idx]
        if res:
            title = res.get('title', '')[:47] + '...' if len(res.get('title', '')) > 50 else res.get('title', '')
            status = f"✅ Найдено ({res.get('source', 'Читай-город')})"
            print(f"{idx+1:4} | {isbn:<20} | {status:<25} | {title}")
        else:
            print(f"{idx+1:4} | {isbn:<20} | {'❌ Не найдено':<25} |")

    # Запускаем синхронную функцию parallel_search_with_progress в executor
    loop = asyncio.get_running_loop()
    scraped_results = await loop.run_in_executor(
        None,
        parallel_search_with_progress,
        isbn_list,
        config,
        progress_callback
    )
    print("-" * len(header))
    return scraped_results


# ========== ОСНОВНАЯ ЛОГИКА ==========

async def collect_isbns_from_pdfs(
    directory: str,
    max_workers: Optional[int] = None,
    strict: bool = True,
    include_metadata: bool = False,
    max_pages: int = 10,
    max_concurrent: Optional[int] = None,
) -> List[Tuple[str, Optional[str], str]]:
    """Асинхронно обходит директорию, извлекает ISBN из PDF-файлов (с ограничением по семафору)."""
    results = []
    logger.info(f"Поиск PDF в {directory}...")
    async for pdf_path, isbn, source in scan_pdfs(
        directory=directory,
        max_workers=max_workers,
        strict=strict,
        include_metadata=include_metadata,
        max_pages=max_pages,
        max_concurrent=max_concurrent,
    ):
        results.append((pdf_path, isbn, source))
        if isbn:
            logger.debug(f"[{pdf_path}] -> ISBN: {isbn} ({source})")
        else:
            logger.debug(f"[{pdf_path}] -> ISBN не найден")
    logger.info(f"Обработано PDF: {len(results)}")
    return results


def build_isbn_mapping(
    pdf_results: List[Tuple[str, Optional[str], str]]
) -> Tuple[Dict[str, List[Tuple[str, str, str]]], List[str]]:
    """
    Строит словарь: isbn -> список (путь_к_pdf, источник, isbn_raw).
    Возвращает также список уникальных валидных ISBN.
    """
    mapping = defaultdict(list)
    unique_isbns = []
    for pdf_path, isbn, source in pdf_results:
        if isbn:
            norm_isbn = normalize_isbn(isbn)
            if norm_isbn:
                mapping[norm_isbn].append((pdf_path, source, isbn))
                if norm_isbn not in unique_isbns:
                    unique_isbns.append(norm_isbn)
            else:
                logger.warning(f"Некорректный ISBN {isbn} в файле {pdf_path} пропущен")
    return mapping, unique_isbns


def print_pdf_results_table(
    pdf_results: List[Tuple[str, Optional[str], str]],
    book_data: Dict[str, Optional[Dict[str, Any]]]
) -> None:
    """Выводит итоговую таблицу с результатами для каждого PDF."""
    print("\n" + "=" * 140)
    header = (
        f"{'PDF файл':<60} {'ISBN':<20} {'Источник':<10} "
        f"{'Название':<40} {'Автор(ы)':<30} {'Стр.':<6} {'Год':<5}"
    )
    print(header)
    print("=" * 140)

    for pdf_path, isbn, src in pdf_results:
        display_path = truncate_path(pdf_path, 60)

        if not isbn:
            print(f"{display_path:<60} {'—':<20} {'—':<10} {'❌ ISBN не найден':<40} {'':<30} {'':<6} {'':<5}")
            continue

        norm_isbn = normalize_isbn(isbn)
        if not norm_isbn:
            print(f"{display_path:<60} {isbn:<20} {src:<10} {'⚠️ Некорректный ISBN':<40} {'':<30} {'':<6} {'':<5}")
            continue

        data = book_data.get(norm_isbn)
        if not data:
            print(f"{display_path:<60} {isbn:<20} {src:<10} {'❌ Информация не найдена':<40} {'':<30} {'':<6} {'':<5}")
            continue

        # Усекаем длинные строки
        title = data.get('title', '')[:37] + '...' if len(data.get('title', '')) > 40 else data.get('title', '')
        authors = ', '.join(data.get('authors', []))[:27] + '...' if len(', '.join(data.get('authors', []))) > 30 else ', '.join(data.get('authors', []))
        pages = data.get('pages', '—')
        year = data.get('year', '—')
        source_web = data.get('source', '—')

        print(
            f"{display_path:<60} {isbn:<20} {src:<10} "
            f"{title:<40} {authors:<30} {pages:<6} {year:<5} "
        )
    print("=" * 140)


def save_results_to_json(
    pdf_results: List[Tuple[str, Optional[str], str]],
    book_data: Dict[str, Optional[Dict[str, Any]]],
    output_file: str
) -> None:
    """Сохраняет результаты в JSON-файл."""
    output = []
    for pdf_path, isbn, src in pdf_results:
        record = {
            "pdf_path": pdf_path,
            "isbn_raw": isbn,
            "source_pdf": src,
        }
        if isbn:
            norm_isbn = normalize_isbn(isbn)
            if norm_isbn and norm_isbn in book_data:
                record["book_info"] = book_data[norm_isbn]
            else:
                record["book_info"] = None
        else:
            record["book_info"] = None
        output.append(record)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"Результаты сохранены в {output_file}")


async def async_main(args):
    """Асинхронная основная функция."""

    # ---- Загрузка конфигурации ----
    config_dict = {}
    if args.config:
        try:
            config_dict = load_config_from_json(args.config)
            logger.info(f"Конфигурация загружена из {args.config}")
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            sys.exit(1)

    # Аргументы командной строки, которые переопределяют конфигурацию
    cli_overrides = {}
    if args.headless is not None:
        cli_overrides['headless'] = args.headless
    if args.verbose is not None:
        cli_overrides['verbose'] = args.verbose
    if args.max_pages is not None:
        cli_overrides['max_pages_pdf'] = args.max_pages  # для этапа PDF
    if args.workers is not None:
        cli_overrides['max_workers_pdf'] = args.workers

    merged_config = merge_config(config_dict, cli_overrides)

    # Параметры для этапа извлечения из PDF
    pdf_strict = not merged_config.get('loose', False)
    pdf_include_metadata = merged_config.get('include_metadata', False)
    pdf_max_pages = merged_config.get('max_pages_pdf', 10)
    pdf_max_workers = merged_config.get('max_workers_pdf', None)
    pdf_max_concurrent = merged_config.get('max_concurrent_pdf', None)

    # Параметры для веб-скрапинга (ScraperConfig)
    # Создаём словарь только с теми ключами, которые есть в конструкторе ScraperConfig
    web_config_keys = [
        'headless', 'base_url', 'skip_main_page', 'use_fast_selectors',
        'delay_after_main', 'delay_after_search', 'delay_after_click',
        'delay_between_actions', 'wait_city_modal', 'wait_product_link',
        'poll_interval', 'no_product_phrases', 'max_tabs',
        'rate_limit_phrases', 'rate_limit_initial_delay',
        'rate_limit_coef_start', 'rate_limit_coef_step', 'rate_limit_coef_max',
        'handle_rate_limit', 'keep_browser_open', 'verbose',
        'api_max_concurrent'
    ]
    web_config_dict = {k: merged_config.get(k) for k in web_config_keys if k in merged_config}
    # Если какие-то ключи не заданы, будут использованы значения по умолчанию из ScraperConfig
    web_config = ScraperConfig(**web_config_dict)

    # Настройка логирования
    if web_config.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        pdf_logger.setLevel(logging.DEBUG)
        # Отключаем шумные логи библиотек
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("selenium").setLevel(logging.WARNING)
        logging.getLogger("websockets").setLevel(logging.WARNING)
    else:
        logging.getLogger().setLevel(logging.INFO)
        pdf_logger.setLevel(logging.INFO)

    # ---- Шаг 1: извлечение ISBN из PDF ----
    logger.info("Этап 1: Извлечение ISBN из PDF-файлов")
    pdf_results = await collect_isbns_from_pdfs(
        directory=args.directory,
        max_workers=pdf_max_workers,
        strict=pdf_strict,
        include_metadata=pdf_include_metadata,
        max_pages=pdf_max_pages,
        max_concurrent=pdf_max_concurrent,
    )

    if not pdf_results:
        logger.warning("Не найдено PDF-файлов для обработки")
        return

    # ---- Шаг 2: подготовка списка уникальных ISBN ----
    isbn_mapping, unique_isbns = build_isbn_mapping(pdf_results)
    if not unique_isbns:
        logger.warning("Не найдено ни одного валидного ISBN в PDF-файлах")
        print_pdf_results_table(pdf_results, {})
        return

    logger.info(f"Найдено уникальных ISBN: {len(unique_isbns)}")
    logger.debug(f"Уникальные ISBN: {unique_isbns}")

    # ---- Шаг 3: поиск информации через API и РГБ ----
    logger.info("Этап 2: Поиск через API и РГБ")
    api_results, remaining_isbns, remaining_indices = await run_api_stage(unique_isbns, web_config)

    # Собираем результаты API в словарь
    book_data = {}
    for i, res in enumerate(api_results):
        if res:
            book_data[unique_isbns[i]] = res

    # ---- Шаг 4: скрапинг для оставшихся ISBN ----
    if remaining_isbns:
        logger.info(f"Осталось ISBN для скрапинга: {len(remaining_isbns)}")
        scraped_results = await run_scraping_stage(remaining_isbns, remaining_indices, web_config)
        # Обновляем book_data
        for local_idx, res in enumerate(scraped_results):
            if res:
                isbn = remaining_isbns[local_idx]
                book_data[isbn] = res
    else:
        logger.info("Все ISBN найдены через API/РГБ, скрапинг не требуется.")

    # ---- Шаг 5: вывод итоговой таблицы ----
    print_pdf_results_table(pdf_results, book_data)

    # ---- Шаг 6: сохранение в JSON ----
    if args.output:
        save_results_to_json(pdf_results, book_data, args.output)


def main():
    parser = argparse.ArgumentParser(
        description="Извлечение ISBN из PDF и поиск информации о книгах (API + скрапинг)"
    )
    parser.add_argument("directory", help="Корневая директория для поиска PDF")
    parser.add_argument("--headless", action="store_true",
                        help="Запускать браузер в фоновом режиме")
    parser.add_argument("--config", type=str, default=None,
                        help="Путь к JSON-файлу конфигурации (см. пример)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Подробный вывод")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Сохранить результаты в JSON-файл")

    # Дополнительные часто используемые параметры, которые можно переопределить
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Максимальное число страниц для анализа PDF (0 = все)")
    parser.add_argument("--workers", type=int, default=None,
                        help="Количество процессов для извлечения ISBN (по умолчанию число ядер CPU)")
    parser.add_argument("--loose", action="store_true",
                        help="Нестрогий режим поиска ISBN в PDF (без обязательного префикса ISBN)")
    parser.add_argument("--include-metadata", action="store_true",
                        help="Проверять метаданные PDF в дополнение к тексту")

    args = parser.parse_args()

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()