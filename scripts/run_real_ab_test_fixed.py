#!/usr/bin/env python3
"""
Точка входа для реального A/B тестирования с полным пайплайном.
"""

import asyncio
import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List

# Добавляем путь к корню проекта для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_real_ab_test(books_dir: str = "_books", max_isbns: int = 5):
    """
    Запускает реальное A/B тестирование с полным пайплайном.
    
    Args:
        books_dir: Папка с PDF файлами
        max_isbns: Максимальное количество ISBN для тестирования
    """
    logger.info("=" * 60)
    logger.info("ЗАПУСК РЕАЛЬНОГО A/B ТЕСТИРОВАНИЯ")
    logger.info("=" * 60)
    
    # Шаг 1: Извлечение ISBN из PDF
    logger.info(f"Извлечение ISBN из PDF файлов в {books_dir}...")
    
    try:
        from pdf_extract_isbn import scan_pdfs
        
        pdf_results = scan_pdfs(
            books_dir,
            strict=False,
            include_metadata=True,
            max_pages=10,
            max_concurrent=2
        )
        
        isbns = []
        for result in pdf_results:
            if result.isbn and result.isbn != "null":
                isbns.append(result.isbn)
        
        # Фильтруем действительные ISBN
        valid_isbns = []
        for isbn in isbns:
            clean_isbn = str(isbn).replace("-", "").replace(" ", "").strip()
            if len(clean_isbn) == 10 or len(clean_isbn) == 13:
                if len(clean_isbn) == 10:
                    if clean_isbn[:-1].isdigit() and (clean_isbn[-1].isdigit() or clean_isbn[-1].upper() == 'X'):
                        valid_isbns.append(clean_isbn)
                elif len(clean_isbn) == 13 and clean_isbn.isdigit():
                    valid_isbns.append(clean_isbn)
        
        if len(valid_isbns) > max_isbns:
            valid_isbns = valid_isbns[:max_isbns]
        
        logger.info(f"Извлечено {len(valid_isbns)} ISBN из PDF файлов")
        
    except Exception as e:
        logger.error(f"Ошибка при извлечении ISBN: {e}")
        # Используем тестовые ISBN в случае ошибки
        valid_isbns = [
            "9781835081167",  # Hands-On Python for DevOps
            "9780134173276",  # Python Distilled
            "9785977520966",  # Программирование бекенда на Python
            "9781805125105",  # Security Automation with Python
            "9798868808814",  # Generative AI Apps with LangChain
        ][:max_isbns]
    
    if not valid_isbns:
        logger.error("Не удалось извлечь ISBN для тестирования")
        return
    
    logger.info(f"Для тестирования будет использовано {len(valid_isbns)} ISBN: {', '.join(valid_isbns)}")
    
    # Шаг 2: Запуск старой системы
    logger.info("\n" + "-" * 40)
    logger.info("ЗАПУСК СТАРОЙ СИСТЕМЫ")
    logger.info("-" * 40)
    
    legacy_results = None
    legacy_time = 0
    
    try:
        from scraper import async_parallel_search
        from config import ScraperConfig
        
        config = ScraperConfig()
        config.headless = True
        config.max_tabs = 2
        config.wait_product_link = 5
        
        start_time = time.time()
        legacy_results = await async_parallel_search(valid_isbns, config)
        legacy_time = time.time() - start_time
        
        successful = sum(1 for r in legacy_results if r is not None)
        logger.info(f"Старая система: успешно {successful}/{len(valid_isbns)} ISBN за {legacy_time:.2f} сек")
        
    except Exception as e:
        logger.error(f"Ошибка в старой системе: {e}")
    
    # Шаг 3: Запуск новой системы
    logger.info("\n" + "-" * 40)
    logger.info("ЗАПУСК НОВОЙ СИСТЕМЫ")
    logger.info("-" * 40)
    
    new_results = None
    new_time = 0
    
    try:
        from scraper_core.orchestrator.legacy_adapter import LegacyScraperAdapter
        
        adapter = LegacyScraperAdapter()
        
        start_time = time.time()
        new_results = await adapter.async_parallel_search(valid_isbns)
        new_time = time.time() - start_time
        
        successful = sum(1 for r in new_results if r is not None)
        logger.info(f"Новая система: успешно {successful}/{len(valid_isbns)} ISBN за {new_time:.2f} сек")
        
    except Exception as e:
        logger.error(f"Ошибка в новой системе: {e}")
    
    # Шаг 4: Сравнение результатов
    logger.info("\n" + "-" * 40)
    logger.info("СРАВНЕНИЕ РЕЗУЛЬТАТОВ")
    logger.info("-" * 40)
    
    # Вывод итогов
    print("\n" + "=" * 80)
    print("ИТОГИ РЕАЛЬНОГО A/B ТЕСТИРОВАНИЯ")
    print("=" * 80)
    
    print(f"\n📚 ОБЩАЯ ИНФОРМАЦИЯ:")
    print(f"   Время тестирования: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Протестировано ISBN: {len(valid_isbns)}")
    print(f"   Использованные ISBN: {', '.join(valid_isbns[:3])}{'...' if len(valid_isbns) > 3 else ''}")
    
    if legacy_results is not None:
        legacy_success = sum(1 for r in legacy_results if r is not None)
        legacy_success_rate = legacy_success / len(valid_isbns) if valid_isbns else 0
        print(f"\n🏁 СТАРАЯ СИСТЕМА:")
        print(f"   Успешно: {legacy_success}/{len(valid_isbns)} ({legacy_success_rate:.1%})")
        print(f"   Время выполнения: {legacy_time:.2f} сек")
        print(f"   Среднее время на ISBN: {legacy_time/len(valid_isbns):.2f} сек" if valid_isbns else "")
    
    if new_results is not None:
        new_success = sum(1 for r in new_results if r is not None)
        new_success_rate = new_success / len(valid_isbns) if valid_isbns else 0
        print(f"\n🚀 НОВАЯ СИСТЕМА:")
        print(f"   Успешно: {new_success}/{len(valid_isbns)} ({new_success_rate:.1%})")
        print(f"   Время выполнения: {new_time:.2f} сек")
        print(f"   Среднее время на ISBN: {new_time/len(valid_isbns):.2f} сек" if valid_isbns else "")
    
    if legacy_results is not None and new_results is not None:
        # Сравнение производительности
        if legacy_time > 0:
            performance_improvement = (legacy_time - new_time) / legacy_time
        else:
            performance_improvement = 0
        
        # Сравнение успешности
        success_rate_diff = new_success_rate - legacy_success_rate
        
        print(f"\n📈 СРАВНЕНИЕ:")
        print(f"   Улучшение успешности: {success_rate_diff:+.1%}")
        print(f"   Улучшение производительности: {performance_improvement:+.1%}")
        
        # Рекомендация
        print(f"\n💡 РЕКОМЕНДАЦИЯ:")
        if performance_improvement > 0.1 and success_rate_diff >= 0:
            print("   ✅ Новая система показывает значительное улучшение. Рекомендуется переход на новую архитектуру.")
        elif performance_improvement > 0 and success_rate_diff >= 0:
            print("   ⚠️  Новая система показывает небольшое улучшение. Требуется дополнительное тестирование.")
        else:
            print("   ❌ Новая система не показывает улучшений или ухудшает показатели. Требуется доработка.")
    
    print("\n" + "=" * 80)
    logger.info("A/B тестирование завершено")


def main():
    """Основная функция скрипта."""
    parser = argparse.ArgumentParser(
        description="Запуск реального A/B тестирования с полным пайплайном"
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
    
    # Запускаем тестирование
    asyncio.run(run_real_ab_test(args.books_dir, args.max_isbns))


if __name__ == "__main__":
    main()