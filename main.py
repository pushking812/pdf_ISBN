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
from pdf_extract_isbn import (
    find_pdf_files,
    extract_isbn_from_pdf,
    logger as pdf_logger,
)
from config import ScraperConfig
from utils import normalize_isbn
from drivers import create_chrome_driver
from scraper import (
    run_api_stage,
    async_parallel_search,
    RussianBookScraperUC,
    TabState,
    TabInfo,
)
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
    Аргументы CLI имеют приоритет. Служебные ключи (начинающиеся с _) не копируются.
    """
    merged = {k: v for k, v in base_config.items() if not (isinstance(k, str) and k.startswith('_'))}
    for key, value in cli_args.items():
        if value is not None:  # только если аргумент явно задан
            merged[key] = value
    return merged


# ========== КЭШИ ДЛЯ УСКОРЕНИЯ ПОВТОРНЫХ ЗАПУСКОВ ==========

CACHE_VERSION = 1

# Формат PDF-кэша: ключ = "имя_файла|размер" (без пути); совпадение по имени и размеру = один файл
# entries: { "filename.pdf|12345": { "isbn": str|None, "source": str, "mtime": int, "size": int } }
# Формат кэша книг: { "version": 1, "entries": { "isbn13": { "title", "authors", "source", "pages", "year", ... } } }


def load_pdf_cache(path: str) -> Dict[str, Dict[str, Any]]:
    """Загружает кэш PDF→ISBN. Ключи в формате «имя_файла|размер». При необходимости мигрирует старый формат (путь)."""
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data.get('version') != CACHE_VERSION:
            return {}
        entries = data.get('entries', {})
        return _migrate_pdf_cache_to_name_size(entries)
    except Exception as e:
        logger.warning("Не удалось загрузить PDF-кэш %s: %s", path, e)
        return {}


def save_pdf_cache(entries: Dict[str, Dict[str, Any]], path: str) -> None:
    """Сохраняет кэш PDF→ISBN."""
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({"version": CACHE_VERSION, "entries": entries}, f, ensure_ascii=False, indent=2)
        logger.debug("PDF-кэш сохранён: %s", path)
    except Exception as e:
        logger.warning("Не удалось сохранить PDF-кэш %s: %s", path, e)


def load_isbn_cache(path: str) -> Dict[str, Dict[str, Any]]:
    """Загружает кэш ISBN→данные книги. Возвращает словарь entries или пустой dict."""
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data.get('version') != CACHE_VERSION:
            return {}
        return data.get('entries', {})
    except Exception as e:
        logger.warning("Не удалось загрузить кэш книг %s: %s", path, e)
        return {}


def save_isbn_cache(entries: Dict[str, Dict[str, Any]], path: str) -> None:
    """Сохраняет кэш ISBN→данные книги."""
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({"version": CACHE_VERSION, "entries": entries}, f, ensure_ascii=False, indent=2)
        logger.debug("Кэш книг сохранён: %s", path)
    except Exception as e:
        logger.warning("Не удалось сохранить кэш книг %s: %s", path, e)


def is_book_data_complete(record: Optional[Dict[str, Any]]) -> bool:
    """Считаем запись полной, если есть непустое название (достаточно для отображения)."""
    return bool(record and record.get('title'))


def pdf_cache_key(pdf_path: str) -> Optional[str]:
    """
    Ключ кэша PDF: только имя файла и размер — «имя|размер».
    Один и тот же файл в разных папках даёт один ключ; совпадение по имени и размеру = один файл.
    """
    try:
        st = os.stat(pdf_path)
        return f"{os.path.basename(pdf_path)}|{st.st_size}"
    except OSError:
        return None


def _migrate_pdf_cache_to_name_size(entries: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Переводит старый кэш (ключ = путь) в формат ключ = имя_файла|размер."""
    result = {}
    for key, value in entries.items():
        if "|" in key and key.count("|") == 1 and isinstance(value.get("size"), (int, float)):
            result[key] = value
            continue
        name = os.path.basename(key) if (os.path.sep in key or "/" in key) else key
        size = value.get("size")
        if size is not None:
            result[f"{name}|{size}"] = value
        else:
            result[key] = value
    return result


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
    # Драйвер с таймаутами и стратегией загрузки из конфига (ускоряет скрапинг)
    driver = create_chrome_driver(config)
    delay_tab = getattr(config, 'delay_tab_switch', 0.2)

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
                time.sleep(delay_tab)
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
                time.sleep(delay_tab)
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
    use_pdf_cache: bool = True,
    pdf_cache: Optional[Dict[str, Dict[str, Any]]] = None,
    pdf_cache_path: Optional[str] = None,
    rescan: bool = False,
) -> Tuple[List[Tuple[str, Optional[str], str]], Dict[str, Dict[str, Any]]]:
    """
    Асинхронно обходит директорию, извлекает ISBN из PDF (с опциональным кэшем).
    Возвращает (результаты, обновлённый pdf_cache для сохранения).
    """
    from concurrent.futures import ProcessPoolExecutor

    pdf_cache = pdf_cache if pdf_cache is not None else {}
    pdf_files = await find_pdf_files(directory)
    if not pdf_files:
        logger.info("PDF-файлы не найдены в %s", directory)
        return [], pdf_cache

    use_cache = use_pdf_cache and not rescan
    extract_func = partial(
        extract_isbn_from_pdf,
        strict=strict,
        include_metadata=include_metadata,
        max_pages=max_pages,
    )

    cached_results: Dict[str, Tuple[Optional[str], str]] = {}
    uncached_paths: List[str] = []
    for path in pdf_files:
        cache_key = pdf_cache_key(path)
        if use_cache and cache_key and cache_key in pdf_cache:
            entry = pdf_cache[cache_key]
            cached_results[path] = (entry.get('isbn'), entry.get('source', 'text'))
        else:
            uncached_paths.append(path)

    if cached_results:
        logger.info("Из PDF-кэша: %d файл(ов)", len(cached_results))

    uncached_results: List[Tuple[str, Optional[str], str]] = []
    if uncached_paths:
        loop = asyncio.get_running_loop()
        sem_limit = max_concurrent or max_workers or (os.cpu_count() or 4)
        semaphore = asyncio.Semaphore(sem_limit)
        executor = ProcessPoolExecutor(max_workers=max_workers)

        async def extract_one(p: str) -> Tuple[str, Optional[str], str]:
            async with semaphore:
                isbn, source = await loop.run_in_executor(executor, extract_func, p)
            return p, isbn, source

        try:
            uncached_results = await asyncio.gather(*[extract_one(p) for p in uncached_paths])
            for path, isbn, source in uncached_results:
                ckey = pdf_cache_key(path)
                if ckey:
                    try:
                        st = os.stat(path)
                        pdf_cache[ckey] = {
                            "isbn": isbn,
                            "source": source,
                            "mtime": st.st_mtime,
                            "size": st.st_size,
                        }
                    except OSError:
                        pdf_cache[ckey] = {"isbn": isbn, "source": source}
                if isbn:
                    logger.debug("[%s] -> ISBN: %s (%s)", path, isbn, source)
                else:
                    logger.debug("[%s] -> ISBN не найден", path)
        finally:
            executor.shutdown(wait=True)

    # Итог в порядке pdf_files
    result_list: List[Tuple[str, Optional[str], str]] = []
    uncached_by_path = {t[0]: (t[1], t[2]) for t in uncached_results}
    for path in pdf_files:
        if path in cached_results:
            isbn, source = cached_results[path]
            result_list.append((path, isbn, source))
        else:
            isbn, source = uncached_by_path[path]
            result_list.append((path, isbn, source))

    logger.info("Обработано PDF: %d (из кэша: %d, извлечено: %d)", len(result_list), len(cached_results), len(uncached_paths))
    return result_list, pdf_cache


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


def load_book_data_from_results_json(path: str) -> Dict[str, Dict[str, Any]]:
    """
    Загружает данные о книгах из JSON-отчёта (формат --output).
    Возвращает словарь isbn -> book_info для записей с непустым book_info.
    """
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.warning("Не удалось загрузить JSON отчёта %s: %s", path, e)
        return {}
    result = {}
    for record in data if isinstance(data, list) else []:
        isbn_raw = record.get('isbn_raw')
        book_info = record.get('book_info')
        if not isbn_raw or not book_info or not isinstance(book_info, dict):
            continue
        norm = normalize_isbn(isbn_raw)
        if norm and is_book_data_complete(book_info):
            result[norm] = book_info
    return result


async def async_main(args):
    """Асинхронная основная функция."""

    # ---- Загрузка конфигурации ----
    config_path = args.config
    if config_path is None and os.path.isfile("config.json"):
        config_path = "config.json"
    config_dict = {}
    if config_path:
        try:
            config_dict = load_config_from_json(config_path)
            logger.info("Конфигурация загружена из %s", config_path)
        except Exception as e:
            logger.error("Ошибка загрузки конфигурации: %s", e)
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
    pdf_isbn_cache_path = merged_config.get('pdf_isbn_cache', 'pdf_isbn_cache.json')
    isbn_data_cache_path = merged_config.get('isbn_data_cache', 'isbn_data_cache.json')
    rescan = getattr(args, 'rescan', False)
    use_pdf_cache = not rescan
    use_isbn_cache = not rescan

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
        'api_max_concurrent',
        'page_load_timeout', 'page_load_strategy', 'delay_tab_switch'
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

    # ---- Кэши ----
    pdf_cache = load_pdf_cache(pdf_isbn_cache_path) if use_pdf_cache else {}
    isbn_cache = load_isbn_cache(isbn_data_cache_path) if use_isbn_cache else {}
    # Дополнительно подгружаем данные из JSON-отчёта (--output), если файл есть
    if use_isbn_cache and getattr(args, 'output', None) and os.path.isfile(args.output):
        from_output = load_book_data_from_results_json(args.output)
        if from_output:
            isbn_cache.update(from_output)
            logger.info("Добавлено из JSON-отчёта %s: %d записей", args.output, len(from_output))
    if use_pdf_cache and pdf_cache:
        logger.info("Загружен PDF-кэш: %s (%d записей)", pdf_isbn_cache_path, len(pdf_cache))
    if use_isbn_cache and isbn_cache:
        logger.info("Загружен кэш книг: %s (%d записей)", isbn_data_cache_path, len(isbn_cache))

    # ---- Шаг 1: извлечение ISBN из PDF ----
    logger.info("Этап 1: Извлечение ISBN из PDF-файлов")
    pdf_results, pdf_cache = await collect_isbns_from_pdfs(
        directory=args.directory,
        max_workers=pdf_max_workers,
        strict=pdf_strict,
        include_metadata=pdf_include_metadata,
        max_pages=pdf_max_pages,
        max_concurrent=pdf_max_concurrent,
        use_pdf_cache=use_pdf_cache,
        pdf_cache=pdf_cache,
        pdf_cache_path=pdf_isbn_cache_path,
        rescan=rescan,
    )
    if use_pdf_cache and pdf_isbn_cache_path:
        save_pdf_cache(pdf_cache, pdf_isbn_cache_path)

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

    # ---- Шаг 3: данные по книгам (кэш + API + скрапинг) ----
    book_data: Dict[str, Optional[Dict[str, Any]]] = {}
    for isbn in unique_isbns:
        if use_isbn_cache and isbn in isbn_cache and is_book_data_complete(isbn_cache[isbn]):
            book_data[isbn] = isbn_cache[isbn]
    remaining_to_fetch = [isbn for isbn in unique_isbns if isbn not in book_data]
    if not remaining_to_fetch:
        logger.info("Все ISBN найдены в кэше книг, запросы не выполняются.")
    else:
        if use_isbn_cache and book_data:
            logger.info("Из кэша книг: %d, запрос для: %d", len(book_data), len(remaining_to_fetch))
        logger.info("Этап 2: Поиск через API и РГБ")
        api_results, remaining_isbns, remaining_indices = await run_api_stage(remaining_to_fetch, web_config)
        for i, res in enumerate(api_results):
            if res:
                book_data[remaining_to_fetch[i]] = res

        if remaining_isbns:
            logger.info("Осталось ISBN для скрапинга: %d", len(remaining_isbns))
            scraped_results = await run_scraping_stage(remaining_isbns, remaining_indices, web_config)
            for local_idx, res in enumerate(scraped_results):
                if res:
                    book_data[remaining_isbns[local_idx]] = res
        else:
            logger.info("Все запрошенные ISBN найдены через API/РГБ, скрапинг не требуется.")

    # Обновляем кэш книг новыми данными и сохраняем
    if use_isbn_cache and isbn_data_cache_path:
        isbn_cache.update({k: v for k, v in book_data.items() if v and is_book_data_complete(v)})
        save_isbn_cache(isbn_cache, isbn_data_cache_path)

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
    parser.add_argument("--rescan", action="store_true",
                        help="Игнорировать кэши PDF и книг, выполнить полное извлечение и поиск заново")

    args = parser.parse_args()

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()