"""
Модуль для dual-write в старые кэши при использовании новой архитектуры.

Обеспечивает обратную совместимость, записывая данные одновременно
в старые форматы кэшей (isbn_data_cache.json, pdf_isbn_cache.json)
и в новые форматы, используемые новой архитектурой.
"""

import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Версия кэша для совместимости со старым кодом
CACHE_VERSION = 1


class DualWriteCacheManager:
    """
    Менеджер для записи данных в оба формата кэшей (старый и новый).

    Обеспечивает:
    1. Запись данных о книгах в isbn_data_cache.json (старый формат)
    2. Запись данных о PDF-ISBN в pdf_isbn_cache.json (старый формат)
    3. Запись в новые форматы кэшей (если используются)
    """

    def __init__(
        self,
        isbn_cache_path: str = "isbn_data_cache.json",
        pdf_cache_path: str = "pdf_isbn_cache.json",
        enable_dual_write: bool = True,
    ):
        """
        Инициализация менеджера dual-write.

        Args:
            isbn_cache_path: Путь к старому кэшу данных книг
            pdf_cache_path: Путь к старому кэшу PDF-ISBN
            enable_dual_write: Включить ли dual-write (можно отключить для тестов)
        """
        self.isbn_cache_path = isbn_cache_path
        self.pdf_cache_path = pdf_cache_path
        self.enable_dual_write = enable_dual_write

        # Загружаем существующие кэши для обновления
        self.isbn_cache = self._load_isbn_cache()
        self.pdf_cache = self._load_pdf_cache()

        logger.debug(
            "DualWriteCacheManager инициализирован: "
            f"ISBN кэш: {len(self.isbn_cache)} записей, "
            f"PDF кэш: {len(self.pdf_cache)} записей"
        )

    def _load_isbn_cache(self) -> Dict[str, Dict[str, Any]]:
        """Загружает старый кэш данных книг."""
        if not os.path.isfile(self.isbn_cache_path):
            return {}

        try:
            with open(self.isbn_cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("version") != CACHE_VERSION:
                logger.warning(
                    f"Несовместимая версия кэша в {self.isbn_cache_path}: "
                    f"ожидалось {CACHE_VERSION}, получено {data.get('version')}"
                )
                return {}

            return data.get("entries", {})
        except Exception as e:
            logger.warning(f"Не удалось загрузить кэш книг {self.isbn_cache_path}: {e}")
            return {}

    def _load_pdf_cache(self) -> Dict[str, Dict[str, Any]]:
        """Загружает старый кэш PDF-ISBN."""
        if not os.path.isfile(self.pdf_cache_path):
            return {}

        try:
            with open(self.pdf_cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("version") != CACHE_VERSION:
                logger.warning(
                    f"Несовместимая версия кэша в {self.pdf_cache_path}: "
                    f"ожидалось {CACHE_VERSION}, получено {data.get('version')}"
                )
                return {}

            return data.get("entries", {})
        except Exception as e:
            logger.warning(f"Не удалось загрузить PDF кэш {self.pdf_cache_path}: {e}")
            return {}

    def save_isbn_data(
        self,
        isbn: str,
        book_data: Dict[str, Any],
        only_if_complete: bool = True,
    ) -> bool:
        """
        Сохраняет данные книги в старый кэш (dual-write).

        Args:
            isbn: ISBN книги (нормализованный)
            book_data: Данные книги в формате новой архитектуры
            only_if_complete: Сохранять только если данные полные

        Returns:
            True если данные сохранены, False в противном случае
        """
        if not self.enable_dual_write:
            return False

        # Проверяем, что данные полные (если требуется)
        if only_if_complete and not self._is_book_data_complete(book_data):
            logger.debug(
                f"Данные для ISBN {isbn} неполные, пропускаем сохранение в старый кэш"
            )
            return False

        # Конвертируем данные в старый формат
        old_format_data = self._convert_to_old_isbn_format(book_data)

        # Обновляем кэш в памяти
        self.isbn_cache[isbn] = old_format_data

        # Сохраняем на диск
        return self._save_isbn_cache()

    def save_pdf_data(
        self,
        pdf_key: str,
        pdf_data: Dict[str, Any],
    ) -> bool:
        """
        Сохраняет данные PDF-ISBN в старый кэш (dual-write).

        Args:
            pdf_key: Ключ PDF в формате "filename|filesize"
            pdf_data: Данные PDF в формате новой архитектуры

        Returns:
            True если данные сохранены, False в противном случае
        """
        if not self.enable_dual_write:
            return False

        # Конвертируем данные в старый формат
        old_format_data = self._convert_to_old_pdf_format(pdf_data)

        # Обновляем кэш в памяти
        self.pdf_cache[pdf_key] = old_format_data

        # Сохраняем на диск
        return self._save_pdf_cache()

    def batch_save_isbn_data(
        self,
        isbn_data: Dict[str, Dict[str, Any]],
        only_if_complete: bool = True,
    ) -> int:
        """
        Пакетное сохранение данных книг в старый кэш.

        Args:
            isbn_data: Словарь ISBN -> данные книги
            only_if_complete: Сохранять только если данные полные

        Returns:
            Количество сохраненных записей
        """
        if not self.enable_dual_write:
            return 0

        saved_count = 0
        for isbn, book_data in isbn_data.items():
            if self.save_isbn_data(isbn, book_data, only_if_complete):
                saved_count += 1

        logger.debug(f"Пакетно сохранено {saved_count} записей в ISBN кэш")
        return saved_count

    def _convert_to_old_isbn_format(self, book_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Конвертирует данные книги из нового формата в старый.

        Старый формат:
        {
            "title": str,
            "authors": List[str],
            "source": str,
            "pages": Optional[str],
            "year": Optional[str]
        }
        """
        # Базовые поля
        result = {
            "title": book_data.get("title", ""),
            "authors": book_data.get("authors", []),
            "source": book_data.get("source", "unknown"),
        }

        # Обработка pages (может быть int или str в новом формате)
        pages = book_data.get("pages")
        if pages is not None:
            result["pages"] = str(pages) if not isinstance(pages, str) else pages
        else:
            result["pages"] = None

        # Обработка year (может быть int или str)
        year = book_data.get("year")
        if year is not None:
            result["year"] = str(year) if not isinstance(year, str) else year
        else:
            result["year"] = None

        # Дополнительные поля из нового формата (сохраняем как есть)
        for key in ["publisher", "language", "description", "cover_url"]:
            if key in book_data:
                result[key] = book_data[key]

        return result

    def _convert_to_old_pdf_format(self, pdf_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Конвертирует данные PDF из нового формата в старый.

        Старый формат:
        {
            "isbn": str,
            "source": str,  # "text" или "metadata"
            "mtime": float,
            "size": int
        }
        """
        result = {
            "isbn": pdf_data.get("isbn", ""),
            "source": pdf_data.get("source", "text"),
            "mtime": pdf_data.get("mtime", 0.0),
            "size": pdf_data.get("size", 0),
        }

        # Дополнительные поля из нового формата
        for key in ["pdf_path", "extraction_method", "confidence"]:
            if key in pdf_data:
                result[key] = pdf_data[key]

        return result

    def _is_book_data_complete(self, record: Dict[str, Any]) -> bool:
        """
        Проверяет, полные ли данные книги (совместимость с is_book_data_complete из main.py).
        """
        if not record:
            return False

        title = record.get("title")
        authors = record.get("authors")
        year = record.get("year")

        # Заглушки для каждого поля (из main.py)
        TITLE_STUBS = {"не удалось определить название", "нет названия"}
        AUTHOR_STUBS = {"неизвестный автор"}
        YEAR_STUBS = {"не указан", "0"}

        # Проверка title
        if not title or not isinstance(title, str) or title.strip() in TITLE_STUBS:
            return False

        # Проверка authors
        if not authors or not isinstance(authors, list):
            return False

        # Проверяем, что есть хотя бы один непустой автор
        valid_authors = False
        for author in authors:
            if (
                isinstance(author, str)
                and author.strip()
                and author.strip() not in AUTHOR_STUBS
            ):
                valid_authors = True
                break

        if not valid_authors:
            return False

        # Проверка year
        if year:
            year_str = str(year) if not isinstance(year, str) else year
            if year_str.strip() in YEAR_STUBS:
                return False

        return True

    def _save_isbn_cache(self) -> bool:
        """Сохраняет ISBN кэш на диск."""
        try:
            os.makedirs(
                os.path.dirname(os.path.abspath(self.isbn_cache_path)) or ".",
                exist_ok=True,
            )
            with open(self.isbn_cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"version": CACHE_VERSION, "entries": self.isbn_cache},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.debug(f"ISBN кэш сохранён: {self.isbn_cache_path}")
            return True
        except Exception as e:
            logger.warning(f"Не удалось сохранить ISBN кэш {self.isbn_cache_path}: {e}")
            return False

    def _save_pdf_cache(self) -> bool:
        """Сохраняет PDF кэш на диск."""
        try:
            os.makedirs(
                os.path.dirname(os.path.abspath(self.pdf_cache_path)) or ".",
                exist_ok=True,
            )
            with open(self.pdf_cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"version": CACHE_VERSION, "entries": self.pdf_cache},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.debug(f"PDF кэш сохранён: {self.pdf_cache_path}")
            return True
        except Exception as e:
            logger.warning(f"Не удалось сохранить PDF кэш {self.pdf_cache_path}: {e}")
            return False

    def get_isbn_cache_stats(self) -> Dict[str, Any]:
        """Возвращает статистику по ISBN кэшу."""
        return {
            "path": self.isbn_cache_path,
            "entries_count": len(self.isbn_cache),
            "file_exists": os.path.isfile(self.isbn_cache_path),
            "enable_dual_write": self.enable_dual_write,
        }

    def get_pdf_cache_stats(self) -> Dict[str, Any]:
        """Возвращает статистику по PDF кэшу."""
        return {
            "path": self.pdf_cache_path,
            "entries_count": len(self.pdf_cache),
            "file_exists": os.path.isfile(self.pdf_cache_path),
            "enable_dual_write": self.enable_dual_write,
        }

    def clear_memory_caches(self):
        """Очищает кэши в памяти (но не на диске)."""
        self.isbn_cache.clear()
        self.pdf_cache.clear()
        logger.debug("Кэши в памяти очищены")

    def reload_caches(self):
        """Перезагружает кэши с диска."""
        self.isbn_cache = self._load_isbn_cache()
        self.pdf_cache = self._load_pdf_cache()
        logger.debug("Кэши перезагружены с диска")


# Утилитарные функции для удобного использования
def create_dual_write_manager(
    config: Optional[Dict[str, Any]] = None,
) -> DualWriteCacheManager:
    """
    Создаёт менеджер dual-write на основе конфигурации.

    Args:
        config: Конфигурация с путями к кэшам

    Returns:
        Экземпляр DualWriteCacheManager
    """
    if config is None:
        config = {}

    isbn_cache_path = config.get("isbn_data_cache", "isbn_data_cache.json")
    pdf_cache_path = config.get("pdf_isbn_cache", "pdf_isbn_cache.json")
    enable_dual_write = config.get("enable_dual_write", True)

    return DualWriteCacheManager(
        isbn_cache_path=isbn_cache_path,
        pdf_cache_path=pdf_cache_path,
        enable_dual_write=enable_dual_write,
    )


def save_book_data_with_dual_write(
    isbn: str,
    book_data: Dict[str, Any],
    cache_manager: Optional[DualWriteCacheManager] = None,
    **kwargs,
) -> bool:
    """
    Утилитарная функция для сохранения данных книги с dual-write.

    Args:
        isbn: ISBN книги
        book_data: Данные книги
        cache_manager: Опциональный менеджер кэша
        **kwargs: Дополнительные параметры для save_isbn_data

    Returns:
        True если данные сохранены
    """
    if cache_manager is None:
        cache_manager = create_dual_write_manager()

    return cache_manager.save_isbn_data(isbn, book_data, **kwargs)


def save_pdf_data_with_dual_write(
    pdf_key: str,
    pdf_data: Dict[str, Any],
    cache_manager: Optional[DualWriteCacheManager] = None,
) -> bool:
    """
    Утилитарная функция для сохранения данных PDF с dual-write.

    Args:
        pdf_key: Ключ PDF
        pdf_data: Данные PDF
        cache_manager: Опциональный менеджер кэша

    Returns:
        True если данные сохранены
    """
    if cache_manager is None:
        cache_manager = create_dual_write_manager()

    return cache_manager.save_pdf_data(pdf_key, pdf_data)
