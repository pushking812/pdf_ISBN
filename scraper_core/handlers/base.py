"""
Базовый класс обработчика ресурсов.

Определяет интерфейс для обработчиков различных типов ресурсов
(веб-сайты, API, JSON-LD, таблицы).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ResourceHandler(ABC):
    """Базовый класс обработчика ресурсов."""

    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация обработчика ресурса.

        Args:
            config: Конфигурация ресурса
        """
        self.config = config
        self.resource_config = config  # Для совместимости с существующим кодом
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def fetch_data(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Получение данных по ISBN.

        Args:
            isbn: ISBN номер

        Returns:
            Optional[Dict[str, Any]]: Данные книги или None при ошибке
        """
        pass

    @abstractmethod
    def parse_data(self, raw_data: Any) -> Dict[str, Any]:
        """
        Парсинг сырых данных.

        Args:
            raw_data: Сырые данные для парсинга

        Returns:
            Dict[str, Any]: Структурированные данные книги
        """
        pass

    async def process(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Полный процесс обработки ISBN.

        Args:
            isbn: ISBN номер

        Returns:
            Optional[Dict[str, Any]]: Результат обработки
        """
        try:
            raw_data = await self.fetch_data(isbn)
            if raw_data:
                return self.parse_data(raw_data)
        except Exception as e:
            self.logger.error(f"Ошибка обработки ISBN {isbn}: {e}")

        return None
