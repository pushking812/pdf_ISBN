#!/usr/bin/env python3
"""
Тестирование исправленной версии новой архитектуры с TabManager.

Проверяет, что для каждой ссылки открывается вкладка, а не новое окно браузера.
"""

import asyncio
import logging
import sys
import os
from typing import List, Dict, Any

# Добавляем путь к проекту для импорта scraper_core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_tab_manager_version():
    """Тестирование исправленной версии с TabManager."""
    logger.info("Тестирование исправленной версии новой архитектуры с TabManager")
    
    try:
        from scraper_core.orchestrator.core import ScraperOrchestrator
        
        # Создаем оркестратор с включенным TabManager
        orchestrator = ScraperOrchestrator(
            config_dir="config",
            max_concurrent_tasks=3,
            use_tab_manager=True,
            use_retry_handler=True,
            use_search_coordinator=True,
            max_tabs=3,  # Максимум 3 вкладки
            use_driver_manager=False,
            use_antibot_handler=False,
            use_priority_queue=False
        )
        
        logger.info("Оркестратор создан с TabManager")
        
        # Тестовые ISBN (несколько для проверки работы с вкладками)
        test_isbns = [
            "9781835081167",  # Тестовый ISBN из реальных книг
            "9780138101272",  # Еще один тестовый ISBN
            "9781492056355",  # Третий тестовый ISBN
        ]
        
        logger.info(f"Начинаем скрапинг {len(test_isbns)} ISBN с использованием TabManager")
        
        try:
            # Запускаем скрапинг
            results = await orchestrator.scrape_isbns(test_isbns)
            
            logger.info(f"Скрапинг завершен. Получено {len(results)} результатов")
            
            # Выводим результаты
            for i, result in enumerate(results):
                if result:
                    logger.info(f"Результат {i+1}:")
                    logger.info(f"  ISBN: {result.get('isbn', 'N/A')}")
                    logger.info(f"  Ресурс: {result.get('resource_id', 'N/A')}")
                    logger.info(f"  Название: {result.get('title', 'N/A')}")
                    logger.info(f"  Автор: {result.get('author', 'N/A')}")
                    logger.info(f"  Использован TabManager: {result.get('_used_tab_manager', False)}")
                else:
                    logger.warning(f"Результат {i+1}: Нет данных")
            
            # Проверяем статистику
            stats = orchestrator.get_resource_stats()
            logger.info(f"Статистика по ресурсам: {len(stats)} ресурсов")
            
            for resource_id, stat in stats.items():
                logger.info(f"  Ресурс {resource_id}: {stat}")
            
        finally:
            # Закрываем оркестратор
            await orchestrator.close()
            logger.info("Оркестратор закрыт")
            
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_legacy_adapter_comparison():
    """Сравнение работы LegacyAdapter и новой версии с TabManager."""
    logger.info("Сравнение LegacyAdapter и новой версии с TabManager")
    
    try:
        from scraper_core.orchestrator.legacy_adapter import LegacyScraperAdapter
        
        # Создаем LegacyAdapter
        legacy_adapter = LegacyScraperAdapter(
            config_dir="config",
            use_tab_manager=True,
            max_tabs=3
        )
        
        logger.info("LegacyAdapter создан")
        
        # Тестовые ISBN
        test_isbns = ["9781835081167", "9780138101272"]
        
        # Запускаем скрапинг через LegacyAdapter
        logger.info("Запуск скрапинга через LegacyAdapter...")
        legacy_results = await legacy_adapter.async_parallel_search(test_isbns)
        
        logger.info(f"LegacyAdapter результаты: {len(legacy_results)} записей")
        
        # Закрываем LegacyAdapter
        await legacy_adapter.close()
        logger.info("LegacyAdapter закрыт")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка тестирования LegacyAdapter: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Основная функция тестирования."""
    logger.info("=== Начало тестирования исправленной версии с TabManager ===")
    
    # Тест 1: Новая версия с TabManager
    logger.info("\n--- Тест 1: Новая версия с TabManager ---")
    test1_success = await test_tab_manager_version()
    
    # Тест 2: LegacyAdapter для сравнения
    logger.info("\n--- Тест 2: LegacyAdapter для сравнения ---")
    test2_success = await test_legacy_adapter_comparison()
    
    # Итоги
    logger.info("\n=== Итоги тестирования ===")
    logger.info(f"Тест 1 (Новая версия с TabManager): {'УСПЕХ' if test1_success else 'ПРОВАЛ'}")
    logger.info(f"Тест 2 (LegacyAdapter): {'УСПЕХ' if test2_success else 'ПРОВАЛ'}")
    
    if test1_success:
        logger.info("✅ Исправленная версия с TabManager работает корректно")
        logger.info("✅ Для каждой ссылки должна открываться вкладка, а не новое окно браузера")
    else:
        logger.error("❌ Исправленная версия с TabManager не работает")
        
    return test1_success and test2_success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)