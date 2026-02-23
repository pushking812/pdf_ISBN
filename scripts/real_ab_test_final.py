#!/usr/bin/env python3
"""
Финальная точка входа для реального A/B тестирования с реальными ISBN.

Этот скрипт выполняет:
1. Извлечение реальных ISBN из PDF файлов в папке _books
2. Запуск старой системы (с вкладками) для поиска данных
3. Запуск новой системы (с TabManager) для поиска данных
4. Сравнение результатов и производительности
5. Сохранение результатов в кэш и вывод отчета

Особенности:
- Каждая система запускается в отдельном процессе с собственным драйвером
- Драйверы закрываются между запусками систем
- Используются реальные ISBN из PDF файлов
- Результаты сохраняются для последующего анализа
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
class TestMetrics:
    """Метрики тестирования системы."""
    system_name: str
    total_isbns: int
    found_books: int
    success_rate: float
    total_time: float
    avg_time_per_isbn: float
    errors: List[str]
    sources: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует в словарь."""
        return asdict(self)


@dataclass
class ABTestResult:
    """Результаты A/B тестирования."""
    legacy_metrics: TestMetrics
    new_metrics: TestMetrics
    comparison: Dict[str, Any]
    winner: str
    improvement_percentage: float


class RealABTestPipeline:
    """Пайплайн для реального A/B тестирования."""
    
    def __init__(self, books_dir: str = "_books", max_isbns: int = 5):
        """
        Инициализация пайплайна.
        
        Args:
            books_dir: Папка с PDF файлами
            max_isbns: Максимальное количество ISBN для тестирования
        """
        self.books_dir = books_dir
        self.max_isbns = max_isbns
        self.isbns: List[str] = []
        self.legacy_results: Dict[str, Any] = {}
        self.new_results: Dict[str, Any] = {}
    
    def extract_isbns_from_pdfs(self) -> List[str]:
        """
        Извлекает ISBN из PDF файлов.
        
        Returns:
            Список извлеченных ISBN
        """
        logger.info(f"🔍 Извлечение ISBN из PDF файлов в {self.books_dir}...")
        
        try:
            from pdf_extract_isbn import extract_isbn_from_pdf
            
            # Получаем список PDF файлов
            pdf_files = list(Path(self.books_dir).glob("*.pdf"))
            if not pdf_files:
                logger.error(f"❌ В папке {self.books_dir} не найдено PDF файлов")
                return []
            
            logger.info(f"  Найдено {len(pdf_files)} PDF файлов")
            
            # Ограничиваем количество файлов для тестирования
            test_files = pdf_files[:self.max_isbns]
            
            # Извлекаем ISBN из каждого файла
            isbns = []
            for test_file in test_files:
                isbn, source = extract_isbn_from_pdf(str(test_file), strict=False)
                if isbn:
                    isbns.append(isbn)
                    logger.info(f"  ✅ {test_file.name}: {isbn} ({source})")
                else:
                    logger.info(f"  ⚠️  {test_file.name}: ISBN не найден")
            
            logger.info(f"  Извлечено {len(isbns)} валидных ISBN")
            return isbns
            
        except ImportError as e:
            logger.error(f"Не удалось импортировать модуль pdf_extract_isbn: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка при извлечении ISBN: {e}")
            return []
    
    def _filter_valid_isbns(self, isbns: List[str]) -> List[str]:
        """
        Фильтрует валидные ISBN.
        
        Args:
            isbns: Список ISBN для фильтрации
            
        Returns:
            Отфильтрованный список валидных ISBN
        """
        # Простая фильтрация по длине и наличию только цифр
        valid_isbns = []
        for isbn in isbns:
            if not isbn:
                continue
            # Удаляем дефисы и пробелы
            clean_isbn = ''.join(c for c in isbn if c.isdigit() or c == 'X' or c == 'x')
            if len(clean_isbn) in [10, 13]:
                valid_isbns.append(clean_isbn)
        
        return valid_isbns
    
    def _get_test_isbns(self) -> List[str]:
        """
        Получает тестовые ISBN.
        
        Returns:
            Список ISBN для тестирования
        """
        # Сначала пытаемся извлечь из PDF
        isbns = self.extract_isbns_from_pdfs()
        
        # Если не удалось извлечь, используем тестовые данные
        if not isbns:
            logger.warning("Не удалось извлечь ISBN из PDF, используем тестовые данные")
            test_isbns = [
                "9785171125953",  # Python. Карманный справочник
                "9785446114426",  # Чистый Python
                "9785446109842",  # Python. К вершинам мастерства
            ]
            isbns = test_isbns[:self.max_isbns]
        
        # Фильтруем валидные ISBN
        valid_isbns = self._filter_valid_isbns(isbns)
        
        if not valid_isbns:
            logger.error("❌ Не удалось получить валидные ISBN для тестирования")
            return []
        
        logger.info(f"📚 ISBN для тестирования: {valid_isbns}")
        return valid_isbns
    
    async def run_legacy_system(self, isbns: List[str]) -> TestMetrics:
        """
        Запускает старую систему (с вкладками).
        
        Args:
            isbns: Список ISBN для поиска
            
        Returns:
            Метрики старой системы
        """
        logger.info("🔄 ЗАПУСК СТАРОЙ СИСТЕМЫ (с вкладками)...")
        
        start_time = time.time()
        errors = []
        found_count = 0
        sources_count = {}
        
        try:
            # Импортируем старую систему
            import sys
            sys.path.insert(0, '.')
            from main import parallel_search_with_progress
            from config import ScraperConfig
            
            # Настраиваем конфигурацию
            config = ScraperConfig()
            config.headless = False
            config.max_tabs = min(3, len(isbns))
            config.wait_product_link = 5
            
            # Создаем простой progress_callback
            def progress_callback(index, result):
                if result and result.get("title"):
                    logger.debug(f"  Прогресс: ISBN {isbns[index]} обработан")
                else:
                    logger.debug(f"  Прогресс: ISBN {isbns[index]} не найден")
            
            # Запускаем поиск
            results = await parallel_search_with_progress(isbns, config, progress_callback)
            
            # Обрабатываем результаты
            for isbn, result in zip(isbns, results):
                if result and result.get("title"):
                    found_count += 1
                    source = result.get("source", "unknown")
                    sources_count[source] = sources_count.get(source, 0) + 1
                    logger.info(f"  ✅ {isbn}: найдено через {source}")
                else:
                    logger.info(f"  ⚠️  {isbn}: не найдено")
            
        except ImportError as e:
            error_msg = f"Не удалось импортировать старую систему: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"Ошибка в старой системе: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        total_time = time.time() - start_time
        success_rate = found_count / len(isbns) if isbns else 0
        
        # Сохраняем результаты
        self.legacy_results = {
            "isbns": isbns,
            "found_count": found_count,
            "total_time": total_time,
            "sources": sources_count
        }
        
        metrics = TestMetrics(
            system_name="Старая система (вкладки)",
            total_isbns=len(isbns),
            found_books=found_count,
            success_rate=success_rate,
            total_time=total_time,
            avg_time_per_isbn=total_time / len(isbns) if isbns else 0,
            errors=errors,
            sources=sources_count
        )
        
        logger.info(f"✅ Старая система завершена: {found_count}/{len(isbns)} книг за {total_time:.2f}с")
        return metrics
    
    async def run_new_system(self, isbns: List[str]) -> TestMetrics:
        """
        Запускает новую систему (с TabManager).
        
        Args:
            isbns: Список ISBN для поиска
            
        Returns:
            Метрики новой системы
        """
        logger.info("🚀 ЗАПУСК НОВОЙ СИСТЕМЫ (с TabManager)...")
        
        start_time = time.time()
        errors = []
        found_count = 0
        sources_count = {}
        
        try:
            # Импортируем новую систему
            from scraper_core.orchestrator.legacy_adapter import LegacyScraperAdapter
            
            # Создаем адаптер с настройками для использования TabManager
            adapter = LegacyScraperAdapter(
                config_dir="config",
                max_concurrent_tasks=min(3, len(isbns)),
                enable_dual_write=True
            )
            
            # Запускаем поиск
            results = await adapter.async_parallel_search(isbns)
            
            # Обрабатываем результаты
            for isbn, result in zip(isbns, results):
                if result:
                    found_count += 1
                    source = result.get("source", "new_system")
                    sources_count[source] = sources_count.get(source, 0) + 1
                    logger.info(f"  ✅ {isbn}: найдено через {source}")
                else:
                    logger.info(f"  ⚠️  {isbn}: не найдено")
            
            # Закрываем адаптер (и драйверы)
            if hasattr(adapter, 'orchestrator'):
                await adapter.orchestrator.close()
            
        except ImportError as e:
            error_msg = f"Не удалось импортировать новую систему: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"Ошибка в новой системе: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        total_time = time.time() - start_time
        success_rate = found_count / len(isbns) if isbns else 0
        
        # Сохраняем результаты
        self.new_results = {
            "isbns": isbns,
            "found_count": found_count,
            "total_time": total_time,
            "sources": sources_count
        }
        
        metrics = TestMetrics(
            system_name="Новая система (TabManager)",
            total_isbns=len(isbns),
            found_books=found_count,
            success_rate=success_rate,
            total_time=total_time,
            avg_time_per_isbn=total_time / len(isbns) if isbns else 0,
            errors=errors,
            sources=sources_count
        )
        
        logger.info(f"✅ Новая система завершена: {found_count}/{len(isbns)} книг за {total_time:.2f}с")
        return metrics
    
    def compare_results(self, legacy_metrics: TestMetrics, new_metrics: TestMetrics) -> Dict[str, Any]:
        """
        Сравнивает результаты двух систем.
        
        Args:
            legacy_metrics: Метрики старой системы
            new_metrics: Метрики новой системы
            
        Returns:
            Словарь с результатами сравнения
        """
        logger.info("📊 СРАВНЕНИЕ РЕЗУЛЬТАТОВ...")
        
        comparison = {
            "success_rate": {
                "legacy": legacy_metrics.success_rate,
                "new": new_metrics.success_rate,
                "difference": new_metrics.success_rate - legacy_metrics.success_rate,
                "difference_percent": ((new_metrics.success_rate - legacy_metrics.success_rate) / legacy_metrics.success_rate * 100) if legacy_metrics.success_rate > 0 else 0
            },
            "total_time": {
                "legacy": legacy_metrics.total_time,
                "new": new_metrics.total_time,
                "difference": new_metrics.total_time - legacy_metrics.total_time,
                "difference_percent": ((new_metrics.total_time - legacy_metrics.total_time) / legacy_metrics.total_time * 100) if legacy_metrics.total_time > 0 else 0
            },
            "avg_time_per_isbn": {
                "legacy": legacy_metrics.avg_time_per_isbn,
                "new": new_metrics.avg_time_per_isbn,
                "difference": new_metrics.avg_time_per_isbn - legacy_metrics.avg_time_per_isbn,
                "difference_percent": ((new_metrics.avg_time_per_isbn - legacy_metrics.avg_time_per_isbn) / legacy_metrics.avg_time_per_isbn * 100) if legacy_metrics.avg_time_per_isbn > 0 else 0
            },
            "found_books": {
                "legacy": legacy_metrics.found_books,
                "new": new_metrics.found_books,
                "difference": new_metrics.found_books - legacy_metrics.found_books
            }
        }
        
        # Определяем победителя
        winner = "Новая система" if new_metrics.success_rate > legacy_metrics.success_rate else "Старая система"
        if new_metrics.success_rate == legacy_metrics.success_rate:
            if new_metrics.total_time < legacy_metrics.total_time:
                winner = "Новая система (быстрее)"
            elif new_metrics.total_time > legacy_metrics.total_time:
                winner = "Старая система (быстрее)"
            else:
                winner = "Ничья"
        
        improvement_percentage = comparison["success_rate"]["difference_percent"]
        
        return {
            "comparison": comparison,
            "winner": winner,
            "improvement_percentage": improvement_percentage
        }
    
    async def run_full_pipeline(self) -> ABTestResult:
        """
        Запускает полный пайплайн A/B тестирования.
        
        Returns:
            Результаты A/B тестирования
        """
        logger.info("=" * 60)
        logger.info("🚀 ЗАПУСК РЕАЛЬНОГО A/B ТЕСТИРОВАНИЯ")
        logger.info("=" * 60)
        
        # Шаг 1: Получение ISBN для тестирования
        self.isbns = self._get_test_isbns()
        if not self.isbns:
            logger.error("❌ Не удалось получить ISBN для тестирования")
            return None
        
        logger.info(f"📚 Тестирование {len(self.isbns)} ISBN: {self.isbns}")
        
        # Шаг 2: Запуск старой системы
        legacy_metrics = await self.run_legacy_system(self.isbns)
        
        # Небольшая пауза между системами
        await asyncio.sleep(2)
        
        # Шаг 3: Запуск новой системы
        new_metrics = await self.run_new_system(self.isbns)
        
        # Шаг 4: Сравнение результатов
        comparison_result = self.compare_results(legacy_metrics, new_metrics)
        
        # Шаг 5: Сохранение результатов
        self.save_results(legacy_metrics, new_metrics, comparison_result)
        
        # Шаг 6: Вывод результатов
        self.print_results(legacy_metrics, new_metrics, comparison_result)
        
        return ABTestResult(
            legacy_metrics=legacy_metrics,
            new_metrics=new_metrics,
            comparison=comparison_result["comparison"],
            winner=comparison_result["winner"],
            improvement_percentage=comparison_result["improvement_percentage"]
        )
    
    def save_results(self, legacy_metrics: TestMetrics, new_metrics: TestMetrics, comparison: Dict[str, Any]):
        """Сохраняет результаты тестирования."""
        try:
            results = {
                "timestamp": time.time(),
                "isbns": self.isbns,
                "legacy_system": legacy_metrics.to_dict(),
                "new_system": new_metrics.to_dict(),
                "comparison": comparison,
                "metadata": {
                    "books_dir": self.books_dir,
                    "max_isbns": self.max_isbns
                }
            }
            
            # Сохраняем в файл
            output_file = Path("ab_test_results.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Результаты сохранены в {output_file}")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении результатов: {e}")
    
    def print_results(self, legacy_metrics: TestMetrics, new_metrics: TestMetrics, comparison: Dict[str, Any]):
        """Выводит результаты тестирования."""
        print("\n" + "=" * 120)
        print("📊 РЕЗУЛЬТАТЫ РЕАЛЬНОГО A/B ТЕСТИРОВАНИЯ")
        print("=" * 120)
        
        # Таблица сравнения
        table_data = [
            ["Метрика", "Старая система", "Новая система", "Разница", "Изменение"],
            [
                "Успешность (%)",
                f"{legacy_metrics.success_rate:.1%}",
                f"{new_metrics.success_rate:.1%}",
                f"{comparison['comparison']['success_rate']['difference']:+.1%}",
                f"{comparison['comparison']['success_rate']['difference_percent']:+.1f}%"
            ],
            [
                "Общее время (с)",
                f"{legacy_metrics.total_time:.2f}",
                f"{new_metrics.total_time:.2f}",
                f"{comparison['comparison']['total_time']['difference']:+.2f}",
                f"{comparison['comparison']['total_time']['difference_percent']:+.1f}%"
            ],
            [
                "Среднее время на ISBN (с)",
                f"{legacy_metrics.avg_time_per_isbn:.2f}",
                f"{new_metrics.avg_time_per_isbn:.2f}",
                f"{comparison['comparison']['avg_time_per_isbn']['difference']:+.2f}",
                f"{comparison['comparison']['avg_time_per_isbn']['difference_percent']:+.1f}%"
            ],
            [
                "Найдено книг",
                f"{legacy_metrics.found_books}/{legacy_metrics.total_isbns}",
                f"{new_metrics.found_books}/{new_metrics.total_isbns}",
                f"{comparison['comparison']['found_books']['difference']:+d}",
                "-"
            ]
        ]
        
        print(tabulate(table_data, headers="firstrow", tablefmt="grid"))
        
        # Источники данных
        print("\n📚 ИСТОЧНИКИ ДАННЫХ:")
        print(f"  Старая система: {dict(legacy_metrics.sources)}")
        print(f"  Новая система: {dict(new_metrics.sources)}")
        
        # Ошибки
        if legacy_metrics.errors:
            print(f"\n⚠️  ОШИБКИ СТАРОЙ СИСТЕМЫ:")
            for error in legacy_metrics.errors:
                print(f"  - {error}")
        
        if new_metrics.errors:
            print(f"\n⚠️  ОШИБКИ НОВОЙ СИСТЕМЫ:")
            for error in new_metrics.errors:
                print(f"  - {error}")
        
        # Победитель
        print("\n" + "=" * 120)
        print(f"🏆 ПОБЕДИТЕЛЬ: {comparison['winner']}")
        
        if comparison['improvement_percentage'] > 0:
            print(f"📈 Улучшение: {comparison['improvement_percentage']:+.1f}%")
        elif comparison['improvement_percentage'] < 0:
            print(f"📉 Ухудшение: {comparison['improvement_percentage']:+.1f}%")
        else:
            print("📊 Результаты идентичны")
        
        print("=" * 120)


async def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Реальное A/B тестирование старой и новой систем скрапинга"
    )
    
    parser.add_argument(
        "--books-dir",
        "-b",
        type=str,
        default="_books",
        help="Папка с PDF файлами (по умолчанию: _books)"
    )
    
    parser.add_argument(
        "--max-isbns",
        "-m",
        type=int,
        default=5,
        help="Максимальное количество ISBN для тестирования (по умолчанию: 5)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Подробный вывод"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Запускаем пайплайн
    pipeline = RealABTestPipeline(
        books_dir=args.books_dir,
        max_isbns=args.max_isbns
    )
    
    result = await pipeline.run_full_pipeline()
    
    if result:
        logger.info("✅ A/B тестирование успешно завершено")
        return 0
    else:
        logger.error("❌ A/B тестирование завершилось с ошибкой")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)