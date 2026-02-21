#!/usr/bin/env python3
"""
Модуль для извлечения ISBN из PDF-файлов.
Поддерживает рекурсивный обход директорий, многопроцессорную обработку,
строгий/нестрогий режимы поиска, извлечение из метаданных и текста.
"""

import asyncio
import os
import re
from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Tuple, List, AsyncGenerator
import argparse
import logging
from functools import partial

import fitz  # PyMuPDF
from utils import replace_similar_digits

__all__ = [
    "validate_isbn10",
    "validate_isbn13",
    "find_isbn_in_text",
    "extract_isbn_from_pdf",
    "scan_pdfs",
]

# Настройка логгера
logger = logging.getLogger(__name__)


# ---------- Валидация ISBN ----------
def validate_isbn10(isbn: str) -> bool:
    """Проверка контрольной суммы для ISBN-10."""
    if len(isbn) != 10:
        return False
    total = 0
    for i in range(9):
        if not isbn[i].isdigit():
            return False
        total += int(isbn[i]) * (10 - i)
    last = isbn[9]
    if last == "X":
        total += 10
    elif last.isdigit():
        total += int(last)
    else:
        return False
    return total % 11 == 0


def validate_isbn13(isbn: str) -> bool:
    """Проверка контрольной суммы для ISBN-13."""
    if len(isbn) != 13 or not isbn.isdigit():
        return False
    total = 0
    for i in range(12):
        digit = int(isbn[i])
        total += digit * (1 if i % 2 == 0 else 3)
    check = (10 - (total % 10)) % 10
    return int(isbn[12]) == check


# ---------- Поиск ISBN в тексте ----------
def find_isbn_in_text(text: str, strict: bool = True) -> Optional[str]:
    """
    Ищет ISBN в тексте.
    strict=True: требует наличия префикса 'ISBN' перед номером.
    strict=False: ищет любую последовательность, похожую на ISBN.
    """
    # Заменяем похожие на цифры символы (О/O -> 0 и т.д.) во всём тексте
    text = replace_similar_digits(text)
    # Сначала ISBN-13 (978/979), иначе первые 10 цифр ISBN-13 ошибочно матчатся как ISBN-10
    if strict:
        patterns = [
            r"(?:ISBN(?:-13)?:?\s*)?((?:97[89])[-\s]?(?:\d[-\s]?){9}\d)",  # ISBN-13
            r"(?:ISBN(?:-10)?:?\s*)?((?:\d[-\s]?){9}[\dX])",  # ISBN-10
        ]
    else:
        patterns = [
            r"((?:97[89])[-\s]?(?:\d[-\s]?){9}\d)",  # ISBN-13 без префикса
            r"((?:\d[-\s]?){9}[\dX])",  # ISBN-10 без префикса
        ]
    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            candidate = match.group(1)
            clean = re.sub(r"[^\dX]", "", candidate)
            if len(clean) == 13 and validate_isbn13(clean):
                return clean
            if len(clean) == 10 and validate_isbn10(clean):
                return clean
    return None


# ---------- Извлечение из PDF (внутренние функции, вызываются в процессах) ----------
def _extract_from_text(
    pdf_path: str, strict: bool, max_pages: int
) -> Tuple[Optional[str], str]:
    """Извлекает ISBN из текста PDF (первые max_pages страниц)."""
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            full_text += page.get_text()
        doc.close()
        isbn = find_isbn_in_text(full_text, strict=strict)
        return isbn, "text"
    except Exception as e:
        logger.error("Ошибка при извлечении текста из %s: %s", pdf_path, e)
        return None, "text"


def _extract_from_metadata(pdf_path: str, strict: bool) -> Tuple[Optional[str], str]:
    """Извлекает ISBN из метаданных PDF."""
    try:
        doc = fitz.open(pdf_path)
        metadata = doc.metadata
        doc.close()

        text_parts = []
        for value in metadata.values():
            if value and isinstance(value, str):
                text_parts.append(value)

        if not text_parts:
            return None, "metadata"

        combined_text = " ".join(text_parts)
        isbn = find_isbn_in_text(combined_text, strict=strict)
        return isbn, "metadata"
    except Exception as e:
        logger.error("Ошибка при чтении метаданных %s: %s", pdf_path, e)
        return None, "metadata"


# ---------- Основная функция для вызова извне ----------
def extract_isbn_from_pdf(
    pdf_path: str,
    strict: bool = True,
    include_metadata: bool = False,
    max_pages: int = 10,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Извлекает ISBN из PDF-файла.

    Аргументы:
        pdf_path: путь к PDF-файлу
        strict: если True, требует префикса 'ISBN' (рекомендуется)
        include_metadata: если True, дополнительно проверяет метаданные
        max_pages: максимальное число страниц для анализа (0 = все страницы)

    Возвращает:
        Кортеж (isbn, источник) или (None, None), если ISBN не найден.
        Источник: 'text' или 'metadata'.
    """
    if max_pages <= 0:
        max_pages = float("inf")  # обработать все страницы

    if include_metadata:
        isbn, source = _extract_from_metadata(pdf_path, strict)
        if isbn:
            return isbn, source

    isbn, source = _extract_from_text(pdf_path, strict, max_pages)
    if isbn:
        return isbn, source

    return None, None


# ---------- Асинхронный рекурсивный поиск PDF-файлов ----------
async def find_pdf_files(root_dir: str) -> List[str]:
    """Рекурсивно ищет все PDF-файлы в директории (блокирующая операция вынесена в поток)."""
    loop = asyncio.get_running_loop()
    pdf_files = []

    def walk():
        nonlocal pdf_files
        for dirpath, _, filenames in os.walk(root_dir):
            for f in filenames:
                if f.lower().endswith(".pdf"):
                    full_path = os.path.join(dirpath, f)
                    pdf_files.append(full_path)

    await loop.run_in_executor(None, walk)
    return pdf_files


# ---------- Асинхронное сканирование с многопроцессорной обработкой ----------
async def scan_pdfs(
    directory: str,
    max_workers: Optional[int] = None,
    strict: bool = True,
    include_metadata: bool = False,
    max_pages: int = 10,
    executor: Optional[ProcessPoolExecutor] = None,
    max_concurrent: Optional[int] = None,
) -> AsyncGenerator[Tuple[str, Optional[str], Optional[str]], None]:
    """
    Асинхронно обходит директорию, находит все PDF и извлекает из них ISBN.
    Ограничение параллелизма через семафор (как в этапе API/РГБ веб-скрапера).

    Аргументы:
        directory: корневая директория для поиска
        max_workers: количество параллельных процессов в пуле (по умолчанию число ядер CPU)
        strict: строгий режим поиска
        include_metadata: проверять метаданные
        max_pages: максимальное число страниц для анализа
        executor: внешний ProcessPoolExecutor (если нужно переиспользовать)
        max_concurrent: макс. число одновременно обрабатываемых PDF (семафор).
            Если None — используется max_workers или число ядер CPU.

    Генерирует:
        Кортежи (путь_к_pdf, isbn, источник) для каждого файла (по мере готовности).
    """
    pdf_files = await find_pdf_files(directory)
    if not pdf_files:
        return

    loop = asyncio.get_running_loop()
    own_executor = False
    if executor is None:
        executor = ProcessPoolExecutor(max_workers=max_workers)
        own_executor = True

    # Лимит семафора: явный max_concurrent или max_workers, иначе число ядер
    sem_limit = max_concurrent
    if sem_limit is None:
        sem_limit = max_workers or (os.cpu_count() or 4)
    semaphore = asyncio.Semaphore(sem_limit)

    extract_func = partial(
        extract_isbn_from_pdf,
        strict=strict,
        include_metadata=include_metadata,
        max_pages=max_pages,
    )

    async def process_one(pdf_path: str) -> Tuple[str, Optional[str], Optional[str]]:
        async with semaphore:
            isbn, source = await loop.run_in_executor(executor, extract_func, pdf_path)
        return pdf_path, isbn, source

    try:
        tasks = [asyncio.create_task(process_one(p)) for p in pdf_files]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield result
    finally:
        if own_executor:
            executor.shutdown(wait=True)


# ---------- CLI для тестирования ----------
def main():
    parser = argparse.ArgumentParser(description="Извлечение ISBN из PDF-файлов")
    parser.add_argument("directory", help="Корневая директория для поиска")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Количество параллельных процессов (по умолчанию число ядер CPU)",
    )
    parser.add_argument(
        "--loose",
        action="store_true",
        help="Не требовать префикса 'ISBN' (может давать ложные срабатывания)",
    )
    parser.add_argument(
        "--include-metadata",
        action="store_true",
        help="Дополнительно проверять метаданные",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Максимальное число страниц для анализа (0 = все страницы)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=None,
        help="Макс. число одновременно обрабатываемых PDF (семафор). По умолчанию = --workers или число ядер CPU",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Подробное логирование"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    strict = not args.loose

    async def run():
        async for pdf_path, isbn, source in scan_pdfs(
            directory=args.directory,
            max_workers=args.workers,
            strict=strict,
            include_metadata=args.include_metadata,
            max_pages=args.max_pages,
            max_concurrent=args.max_concurrent,
        ):
            if isbn:
                print(f"[{pdf_path}] -> ISBN: {isbn} (источник: {source})")
            else:
                print(f"[{pdf_path}] -> ISBN не найден")

    asyncio.run(run())


if __name__ == "__main__":
    main()
