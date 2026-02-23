#!/usr/bin/env python3
"""
Демонстрация полного пайплайна работы системы:
1. Извлечение ISBN из PDF файлов
2. Поиск данных через API клиентов (Google Books, Open Library, РГБ)
3. Парсинг данных с веб-сайтов (Читай-город, Book.ru, RSL)
4. Обработка и объединение данных
5. Сохранение в кэш
6. Отображение полученных данных
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import pandas as pd
from tabulate import tabulate

# Добавляем путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class BookData:
    """Структура данных о книге."""
    isbn: str
    title: Optional[str] = None
    authors: List[str] = None
    publisher: Optional[str] = None
    year: Optional[str] = None
    pages: Optional[int] = None
    price: Optional[str] = None
    sources: List[str] = None
    extracted_from: Optional[str] = None
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []
        if self.sources is None:
            self.sources = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует в словарь."""
        return asdict(self)
    
    def merge(self, other: 'BookData'):
        """Объединяет данные из другого источника."""
        if not self.title and other.title:
            self.title = other.title
        if not self.authors and other.authors:
            self.authors = other.authors
        if not self.publisher and other.publisher:
            self.publisher = other.publisher
        if not self.year and other.year:
            self.year = other.year
        if not self.pages and other.pages:
            self.pages = other.pages
        if not self.price and other.price:
            self.price = other.price
        if other.sources:
            self.sources.extend(other.sources)
        if other.extracted_from:
            self.extracted_from = other.extracted_from


class FullPipeline:
    """Полный пайплайн обработки книг."""
    
    def __init__(self, use_new_architecture: bool = False):
        """
        Инициализация пайплайна.
        
        Args:
            use_new_architecture: Если True, использовать новую архитектуру для веб-скрапинга.
                                  Если False, использовать старую архитектуру с вкладками.
        """
        self.books_data: Dict[str, BookData] = {}
        self.use_new_architecture = use_new_architecture
        self.new_architecture_used = False  # Флаг, чтобы избежать дублирования
    
    async def extract_isbns_from_pdfs(self, books_dir: str = "_books", limit: int = 3) -> List[str]:
        """
        Извлекает ISBN из PDF файлов.
        
        Args:
            books_dir: Папка с PDF файлами
            limit: Ограничение количества файлов
            
        Returns:
            Список извлеченных ISBN
        """
        logger.info(f"🔍 Извлечение ISBN из PDF файлов в {books_dir}...")
        
        try:
            from pdf_extract_isbn import scan_pdfs
            
            # Получаем список PDF файлов
            pdf_files = list(Path(books_dir).glob("*.pdf"))
            if not pdf_files:
                logger.warning(f"PDF файлы не найдены в {books_dir}")
                return []
            
            # Ограничиваем количество
            pdf_files = pdf_files[:limit]
            
            isbns = []
            for pdf_file in pdf_files:
                try:
                    # Извлекаем ISBN из одного файла
                    from pdf_extract_isbn import extract_isbn_from_pdf
                    
                    isbn, source = extract_isbn_from_pdf(
                        str(pdf_file),
                        strict=False,  # loose=True эквивалентно strict=False
                        include_metadata=True,
                        max_pages=5
                    )
                    
                    if isbn:
                        isbns.append(isbn)
                        logger.info(f"  📖 {pdf_file.name} -> ISBN: {isbn} (источник: {source})")
                        
                        # Сохраняем информацию о источнике
                        book_data = BookData(
                            isbn=isbn,
                            extracted_from=pdf_file.name
                        )
                        self.books_data[isbn] = book_data
                        
                except Exception as e:
                    logger.error(f"  ❌ Ошибка при обработке {pdf_file.name}: {e}")
            
            logger.info(f"✅ Извлечено {len(isbns)} ISBN из {len(pdf_files)} PDF файлов")
            return isbns
            
        except ImportError as e:
            logger.error(f"Не удалось импортировать модуль pdf_extract_isbn: {e}")
            # Используем тестовые ISBN
            return self._get_test_isbns(limit)
        except Exception as e:
            logger.error(f"Ошибка при извлечении ISBN: {e}")
            return self._get_test_isbns(limit)
    
    def _get_test_isbns(self, limit: int = 3) -> List[str]:
        """Возвращает тестовые ISBN."""
        test_isbns = [
            "9781835081167",  # Hands-On Python for DevOps
            "9780134173276",  # Python Distilled
            "9785977520966",  # Программирование бекенда на Python
            "9781805125105",  # Security Automation with Python
            "9798868808814",  # Generative AI Apps with LangChain
        ]
        
        isbns = test_isbns[:limit]
        logger.info(f"Используются тестовые ISBN: {isbns}")
        
        # Создаем записи для тестовых ISBN
        for isbn in isbns:
            self.books_data[isbn] = BookData(isbn=isbn, extracted_from="test_data")
        
        return isbns
    
    async def search_via_api_clients(self, isbns: List[str]):
        """
        Поиск данных через API клиентов.
        
        Args:
            isbns: Список ISBN для поиска
        """
        logger.info(f"🌐 Поиск данных через API клиентов для {len(isbns)} ISBN...")
        
        for isbn in isbns:
            try:
                # Пытаемся использовать Google Books API
                from api_clients import GoogleBooksClient
                
                client = GoogleBooksClient()
                result = await client.search_by_isbn(isbn)
                
                if result:
                    book_data = BookData(
                        isbn=isbn,
                        title=result.get("title"),
                        authors=result.get("authors", []),
                        publisher=result.get("publisher"),
                        year=result.get("published_date"),
                        pages=result.get("page_count"),
                        sources=["Google Books API"]
                    )
                    
                    # Объединяем с существующими данными
                    if isbn in self.books_data:
                        self.books_data[isbn].merge(book_data)
                    else:
                        self.books_data[isbn] = book_data
                    
                    logger.info(f"  ✅ {isbn}: найдено через Google Books API")
                else:
                    logger.info(f"  ⚠️  {isbn}: не найдено в Google Books API")
                    
            except ImportError:
                logger.warning("  📝 Модуль api_clients не доступен, пропускаем API поиск")
                break
            except Exception as e:
                logger.error(f"  ❌ Ошибка при поиске через API для {isbn}: {e}")
    
    async def scrape_via_web_parsers(self, isbns: List[str]):
        """
        Парсинг данных с веб-сайтов с использованием вкладок браузера.
        
        Args:
            isbns: Список ISBN для парсинга
        """
        logger.info(f"🕸️  Парсинг данных с веб-сайтов для {len(isbns)} ISBN...")
        
        # Если установлен флаг использования новой архитектуры, используем её
        if self.use_new_architecture:
            logger.info("  Использование новой архитектуры (установлено в параметрах)...")
            await self.use_new_architecture(isbns)
            self.new_architecture_used = True
            return
        
        try:
            # Прямой импорт старой архитектуры для гарантированного использования вкладок
            import sys
            sys.path.insert(0, '.')
            
            # Импортируем напрямую из main.py, который использует старую архитектуру
            from main import parallel_search_with_progress
            
            logger.info(f"  Запуск веб-скрапинга с вкладками (старая архитектура)...")
            
            # Используем конфигурацию по умолчанию
            import asyncio
            from config import ScraperConfig
            
            config = ScraperConfig()
            config.headless = True
            config.max_tabs = min(3, len(isbns))
            config.wait_product_link = 5
            
            # Запускаем скрапинг через старую архитектуру
            results = await parallel_search_with_progress(isbns, config)
            
            success_count = 0
            for isbn, result in zip(isbns, results):
                if result and result.get("title"):
                    book_data = BookData(
                        isbn=isbn,
                        title=result.get("title"),
                        authors=result.get("authors", []),
                        price=result.get("price"),
                        sources=[result.get("source", "web_scraper")]
                    )
                    
                    # Объединяем с существующими данными
                    if isbn in self.books_data:
                        self.books_data[isbn].merge(book_data)
                    else:
                        self.books_data[isbn] = book_data
                    
                    logger.info(f"  ✅ {isbn}: найдено через веб-скрапинг")
                    success_count += 1
                else:
                    logger.info(f"  ⚠️  {isbn}: не найдено через веб-скрапинг")
            
            logger.info(f"  Старая архитектура: найдено {success_count} из {len(isbns)} книг")
            
            # Если старая архитектура не нашла ни одной книги, пробуем новую как запасной вариант
            if success_count == 0:
                logger.info("  Старая архитектура не нашла данные, пробуем новую архитектуру...")
                await self.use_new_architecture(isbns)
                self.new_architecture_used = True
                    
        except ImportError as e:
            logger.error(f"Не удалось импортировать модуль main: {e}")
            logger.info("  Пробуем использовать новую архитектуру как запасной вариант...")
            await self.use_new_architecture(isbns)
            self.new_architecture_used = True
        except Exception as e:
            logger.error(f"Ошибка при веб-скрапинге: {e}")
            logger.info("  Пробуем использовать новую архитектуру как запасной вариант...")
            await self.use_new_architecture(isbns)
            self.new_architecture_used = True
    
    async def use_new_architecture(self, isbns: List[str]):
        """
        Использование новой архитектуры для поиска данных.
        
        Args:
            isbns: Список ISBN для поиска
        """
        logger.info(f"🚀 Использование новой архитектуры для {len(isbns)} ISBN...")
        
        try:
            from scraper_core.orchestrator.legacy_adapter import LegacyScraperAdapter
            
            adapter = LegacyScraperAdapter()
            results = await adapter.async_parallel_search(isbns)
            
            for isbn, result in zip(isbns, results):
                if result:
                    book_data = BookData(
                        isbn=isbn,
                        title=result.get("title"),
                        authors=result.get("authors", []),
                        price=result.get("price"),
                        sources=[f"new_arch_{result.get('source', 'unknown')}"]
                    )
                    
                    # Объединяем с существующими данными
                    if isbn in self.books_data:
                        self.books_data[isbn].merge(book_data)
                    else:
                        self.books_data[isbn] = book_data
                    
                    logger.info(f"  ✅ {isbn}: найдено через новую архитектуру")
                else:
                    logger.info(f"  ⚠️  {isbn}: не найдено через новую архитектуру")
                    
        except ImportError as e:
            logger.error(f"Не удалось импортировать новую архитектуру: {e}")
        except Exception as e:
            logger.error(f"Ошибка в новой архитектуре: {e}")
    
    def save_to_cache(self):
        """Сохраняет данные в кэш."""
        logger.info("💾 Сохранение данных в кэш...")
        
        try:
            # Сохраняем в isbn_data_cache.json
            cache_data = {
                "version": 1,
                "entries": {}
            }
            
            for isbn, book_data in self.books_data.items():
                cache_data["entries"][isbn] = book_data.to_dict()
            
            with open("isbn_data_cache.json", "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Данные {len(self.books_data)} книг сохранены в isbn_data_cache.json")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении в кэш: {e}")
    
    def display_results(self):
        """Отображает полученные данные."""
        logger.info("📊 Отображение полученных данных...")
        
        if not self.books_data:
            print("❌ Нет данных для отображения")
            return
        
        # Преобразуем данные в таблицу
        table_data = []
        for isbn, book_data in self.books_data.items():
            table_data.append({
                "ISBN": isbn,
                "Название": book_data.title or "Не найдено",
                "Авторы": ", ".join(book_data.authors) if book_data.authors else "Неизвестно",
                "Год": book_data.year or "Неизвестно",
                "Цена": book_data.price or "Неизвестно",
                "Источники": ", ".join(book_data.sources) if book_data.sources else "Нет данных"
            })
        
        # Выводим таблицу
        print("\n" + "=" * 120)
        print("РЕЗУЛЬТАТЫ ПОЛНОГО ПАЙПЛАЙНА ОБРАБОТКИ КНИГ")
        print("=" * 120)
        
        df = pd.DataFrame(table_data)
        print(tabulate(df, headers="keys", tablefmt="grid", showindex=False))
        
        # Статистика
        print("\n" + "=" * 120)
        print("СТАТИСТИКА:")
        print(f"  Всего обработано ISBN: {len(self.books_data)}")
        
        found_books = sum(1 for b in self.books_data.values() if b.title)
        print(f"  Найдено данных: {found_books} ({found_books/len(self.books_data):.1%})")
        
        sources_count = {}
        for book_data in self.books_data.values():
            for source in book_data.sources:
                sources_count[source] = sources_count.get(source, 0) + 1
        
        if sources_count:
            print("  Источники данных:")
            for source, count in sources_count.items():
                print(f"    - {source}: {count} книг")
        
        print("=" * 120)
    
    async def run_full_pipeline(self, books_dir: str = "_books", limit: int = 3):
        """
        Запускает полный пайплайн.
        
        Args:
            books_dir: Папка с PDF файлами
            limit: Ограничение количества ISBN
        """
        logger.info("🚀 ЗАПУСК ПОЛНОГО ПАЙПЛАЙНА ОБРАБОТКИ КНИГ")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Шаг 1: Извлечение ISBN из PDF
        isbns = await self.extract_isbns_from_pdfs(books_dir, limit)
        
        if not isbns:
            logger.error("❌ Не удалось извлечь ISBN для обработки")
            return
        
        # Шаг 2: Поиск через API клиентов
        await self.search_via_api_clients(isbns)
        
        # Шаг 3: Парсинг через веб-скрапинг (использует либо старую, либо новую архитектуру)
        await self.scrape_via_web_parsers(isbns)
        
        # Шаг 4: Использование новой архитектуры только если она не была использована ранее
        # и если мы хотим сравнить обе системы (для A/B тестирования)
        if not self.new_architecture_used and not self.use_new_architecture:
            logger.info("🔬 Запуск новой архитектуры для сравнения (A/B тестирование)...")
            await self.use_new_architecture(isbns)
        
        # Шаг 5: Сохранение в кэш
        self.save_to_cache()
        
        # Шаг 6: Отображение результатов
        self.display_results()
        
        total_time = time.time() - start_time
        logger.info(f"✅ Пайплайн завершен за {total_time:.2f} секунд")


async def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Демонстрация полного пайплайна обработки книг"
    )
    
    parser.add_argument(
        "--books-dir",
        "-b",
        type=str,
        default="_books",
        help="Папка с PDF файлами (по умолчанию: _books)"
    )
    
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=3,
        help="Ограничение количества ISBN для обработки (по умолчанию: 3)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Подробный вывод"
    )
    
    parser.add_argument(
        "--use-new-architecture",
        "-n",
        action="store_true",
        help="Использовать новую архитектуру вместо старой для веб-скрапинга"
    )
    
    parser.add_argument(
        "--compare-both",
        "-c",
        action="store_true",
        help="Запустить обе системы для сравнения (A/B тестирование)"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Если указан флаг сравнения, используем старую архитектуру по умолчанию,
    # но разрешаем запуск новой для сравнения
    if args.compare_both:
        logger.info("🔬 Режим A/B тестирования: будут запущены обе системы для сравнения")
        pipeline = FullPipeline(use_new_architecture=False)
        await pipeline.run_full_pipeline(args.books_dir, args.limit)
    else:
        # Используем выбранную архитектуру
        pipeline = FullPipeline(use_new_architecture=args.use_new_architecture)
        await pipeline.run_full_pipeline(args.books_dir, args.limit)


if __name__ == "__main__":
    asyncio.run(main())