"""
Обработчик ISBN для скрапера.

Обеспечивает валидацию, нормализацию и обработку ISBN номеров
для использования в скрапинге.
"""

from typing import List, Optional, Dict, Any
import logging
from .utils import (
    validate_isbn10,
    validate_isbn13,
    normalize_isbn,
    extract_isbn_from_text,
)

logger = logging.getLogger(__name__)


class ISBNProcessor:
    """Обработчик ISBN номеров."""

    def __init__(self, strict_validation: bool = True):
        """
        Инициализация обработчика ISBN.

        Args:
            strict_validation: Строгая валидация ISBN (только корректные номера)
        """
        self.strict_validation = strict_validation

    def normalize_isbn(self, isbn: str) -> str:
        """
        Нормализация ISBN номера.

        Args:
            isbn: ISBN номер для нормализации

        Returns:
            str: Нормализованный ISBN (без дефисов и пробелов)
        """
        return normalize_isbn(isbn)

    def validate_isbn(self, isbn: str) -> bool:
        """
        Валидация ISBN номера.

        Args:
            isbn: ISBN номер для валидации

        Returns:
            bool: True если ISBN валиден
        """
        normalized = self.normalize_isbn(isbn)

        if len(normalized) == 10:
            return validate_isbn10(normalized)
        elif len(normalized) == 13:
            return validate_isbn13(normalized)
        else:
            return False

    def process_isbn(self, raw_isbn: str) -> Optional[str]:
        """
        Обработка ISBN номера: нормализация и валидация.

        Args:
            raw_isbn: Сырой ISBN номер

        Returns:
            Optional[str]: Нормализованный ISBN или None если невалиден
        """
        normalized = self.normalize_isbn(raw_isbn)

        if self.strict_validation:
            if not self.validate_isbn(normalized):
                logger.warning(f"Невалидный ISBN: {raw_isbn} -> {normalized}")
                return None

        return normalized

    def process_isbn_list(self, raw_isbns: List[str]) -> List[str]:
        """
        Обработка списка ISBN номеров.

        Args:
            raw_isbns: Список сырых ISBN номеров

        Returns:
            List[str]: Список нормализованных валидных ISBN
        """
        processed = []

        for raw_isbn in raw_isbns:
            processed_isbn = self.process_isbn(raw_isbn)
            if processed_isbn:
                processed.append(processed_isbn)

        logger.info(f"Обработано ISBN: {len(processed)}/{len(raw_isbns)} валидных")
        return processed

    def extract_isbn_from_text(self, text: str) -> Optional[str]:
        """
        Извлечение ISBN из текста.

        Args:
            text: Текст для поиска ISBN

        Returns:
            Optional[str]: Найденный ISBN или None
        """
        return extract_isbn_from_text(text, strict=self.strict_validation)

    def batch_process(
        self, items: List[Dict[str, Any]], isbn_field: str = "isbn"
    ) -> List[Dict[str, Any]]:
        """
        Пакетная обработка элементов с ISBN полями.

        Args:
            items: Список словарей с ISBN полями
            isbn_field: Название поля с ISBN

        Returns:
            List[Dict[str, Any]]: Обработанные элементы с нормализованными ISBN
        """
        processed_items = []

        for item in items:
            if isbn_field in item:
                raw_isbn = item[isbn_field]
                processed_isbn = self.process_isbn(raw_isbn)

                if processed_isbn:
                    item[isbn_field] = processed_isbn
                    processed_items.append(item)
                else:
                    logger.debug(f"Пропущен невалидный ISBN: {raw_isbn}")
            else:
                # Элемент без ISBN поля - добавляем как есть
                processed_items.append(item)

        return processed_items
