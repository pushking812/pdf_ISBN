#!/usr/bin/env python3
"""
Скрипт для подготовки реальных ISBN из папки _books для A/B тестирования.

Извлекает ISBN из pdf_isbn_cache.json или запускает извлечение из PDF файлов,
затем сохраняет список ISBN в файл для использования в A/B тестировании.
"""

import json
import argparse
import logging
import sys
from pathlib import Path
from typing import List, Set

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_isbns_from_cache(cache_path: str) -> List[str]:
    """
    Загружает ISBN из кэша PDF.
    
    Args:
        cache_path: Путь к файлу pdf_isbn_cache.json
        
    Returns:
        Список уникальных ISBN
    """
    isbns = set()
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        
        entries = cache_data.get("entries", {})
        
        for entry_key, entry_data in entries.items():
            isbn = entry_data.get("isbn")
            if isbn and isbn != "null" and isbn is not None:
                # Проверяем, что ISBN выглядит как действительный (цифры или X)
                if isinstance(isbn, str) and (isbn.replace("-", "").replace(" ", "").isdigit() or 'X' in isbn):
                    isbns.add(isbn)
        
        logger.info(f"Загружено {len(isbns)} уникальных ISBN из кэша {cache_path}")
        
    except FileNotFoundError:
        logger.warning(f"Файл кэша {cache_path} не найден")
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при чтении JSON из {cache_path}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при загрузке ISBN из кэша: {e}")
    
    return list(isbns)


def extract_isbns_from_pdfs(books_dir: str, max_files: int = 20) -> List[str]:
    """
    Извлекает ISBN из PDF файлов в указанной директории.
    
    Args:
        books_dir: Путь к папке с PDF файлами
        max_files: Максимальное количество файлов для обработки
        
    Returns:
        Список извлеченных ISBN
    """
    try:
        # Импортируем модуль извлечения ISBN
        from pdf_extract_isbn import scan_pdfs
        
        logger.info(f"Извлечение ISBN из PDF файлов в {books_dir}...")
        
        # Запускаем извлечение
        results = scan_pdfs(books_dir, strict=False, include_metadata=True, max_pages=10)
        
        isbns = []
        for result in results:
            if result.isbn:
                isbns.append(result.isbn)
        
        logger.info(f"Извлечено {len(isbns)} ISBN из PDF файлов")
        return isbns
        
    except ImportError as e:
        logger.error(f"Не удалось импортировать модуль pdf_extract_isbn: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при извлечении ISBN из PDF: {e}")
        return []


def save_isbns_to_file(isbns: List[str], output_path: str):
    """
    Сохраняет список ISBN в файл.
    
    Args:
        isbns: Список ISBN
        output_path: Путь для сохранения
    """
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for isbn in isbns:
                f.write(f"{isbn}\n")
        
        logger.info(f"Сохранено {len(isbns)} ISBN в файл {output_path}")
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении ISBN в файл: {e}")


def filter_valid_isbns(isbns: List[str]) -> List[str]:
    """
    Фильтрует список ISBN, оставляя только действительные.
    
    Args:
        isbns: Список ISBN для фильтрации
        
    Returns:
        Отфильтрованный список действительных ISBN
    """
    valid_isbns = []
    
    for isbn in isbns:
        # Убираем дефисы и пробелы
        clean_isbn = str(isbn).replace("-", "").replace(" ", "").strip()
        
        # Проверяем длину и содержимое
        if len(clean_isbn) == 10 or len(clean_isbn) == 13:
            # ISBN-10 может содержать X в конце
            if len(clean_isbn) == 10:
                if clean_isbn[:-1].isdigit() and (clean_isbn[-1].isdigit() or clean_isbn[-1].upper() == 'X'):
                    valid_isbns.append(clean_isbn)
            # ISBN-13 должен содержать только цифры
            elif len(clean_isbn) == 13 and clean_isbn.isdigit():
                valid_isbns.append(clean_isbn)
    
    logger.info(f"После фильтрации осталось {len(valid_isbns)} действительных ISBN")
    return valid_isbns


def main():
    """Основная функция скрипта."""
    parser = argparse.ArgumentParser(
        description="Подготовка реальных ISBN из папки _books для A/B тестирования"
    )
    
    parser.add_argument(
        "--cache",
        "-c",
        type=str,
        default="pdf_isbn_cache.json",
        help="Путь к файлу кэша ISBN (по умолчанию: pdf_isbn_cache.json)"
    )
    
    parser.add_argument(
        "--books-dir",
        "-b",
        type=str,
        default="_books",
        help="Путь к папке с PDF файлами (по умолчанию: _books)"
    )
    
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="real_isbns.txt",
        help="Путь для сохранения списка ISBN (по умолчанию: real_isbns.txt)"
    )
    
    parser.add_argument(
        "--extract",
        "-e",
        action="store_true",
        help="Принудительно извлекать ISBN из PDF файлов (даже если есть кэш)"
    )
    
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=0,
        help="Ограничить количество ISBN (0 = без ограничения)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Подробный вывод"
    )
    
    args = parser.parse_args()
    
    # Настройка уровня логирования
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    isbns = []
    
    # Загружаем ISBN из кэша, если не требуется принудительное извлечение
    if not args.extract:
        isbns = load_isbns_from_cache(args.cache)
    
    # Если в кэше недостаточно ISBN или требуется принудительное извлечение
    if args.extract or len(isbns) < 10:
        logger.info("Извлечение ISBN из PDF файлов...")
        extracted_isbns = extract_isbns_from_pdfs(args.books_dir)
        
        # Объединяем с ISBN из кэша
        all_isbns = list(set(isbns + extracted_isbns))
        isbns = all_isbns
    
    # Фильтруем действительные ISBN
    valid_isbns = filter_valid_isbns(isbns)
    
    # Ограничиваем количество, если указано
    if args.limit > 0 and len(valid_isbns) > args.limit:
        logger.info(f"Ограничение списка до {args.limit} ISBN")
        valid_isbns = valid_isbns[:args.limit]
    
    # Сохраняем в файл
    if valid_isbns:
        save_isbns_to_file(valid_isbns, args.output)
        
        # Выводим статистику
        print("\n" + "=" * 60)
        print("СТАТИСТИКА ПОДГОТОВКИ РЕАЛЬНЫХ ISBN")
        print("=" * 60)
        print(f"Всего подготовлено ISBN: {len(valid_isbns)}")
        print(f"Файл с ISBN: {args.output}")
        print("\nПервые 10 ISBN:")
        for i, isbn in enumerate(valid_isbns[:10], 1):
            print(f"  {i:2d}. {isbn}")
        if len(valid_isbns) > 10:
            print(f"  ... и еще {len(valid_isbns) - 10} ISBN")
        print("=" * 60)
        
        return 0
    else:
        logger.error("Не удалось подготовить ни одного действительного ISBN")
        return 1


if __name__ == "__main__":
    sys.exit(main())