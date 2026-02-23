"""
Обработчик табличных ресурсов.

Обрабатывает ресурсы с данными в табличном формате (HTML таблицы).
"""

import re
from typing import Dict, Any, Optional, List
import logging

from .base import ResourceHandler

logger = logging.getLogger(__name__)


class TableResourceHandler(ResourceHandler):
    """Обработчик табличных ресурсов."""

    def __init__(self, resource_config: Dict[str, Any]):
        super().__init__(resource_config)
        self.table_selector = resource_config.get("table_selector", "table")
        self.header_row_selector = resource_config.get(
            "header_row_selector", "thead tr"
        )
        self.data_row_selector = resource_config.get("data_row_selector", "tbody tr")
        self.cell_selector = resource_config.get("cell_selector", "td, th")
        self.field_mapping = resource_config.get("field_mapping", {})

    async def fetch_data(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Получение данных с табличного ресурса.

        Args:
            isbn: ISBN для поиска

        Returns:
            Optional[Dict[str, Any]]: Сырые данные или None
        """
        # Табличные данные обычно встроены в HTML, поэтому используем веб-обработчик
        from .web_handler import WebResourceHandler

        web_handler = WebResourceHandler(self.resource_config)
        try:
            raw_data = await web_handler.fetch_data(isbn)
            if raw_data and "html" in raw_data:
                return raw_data
            return None
        finally:
            await web_handler.close()

    def parse_data(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Парсинг табличных данных.

        Args:
            raw_data: Сырые данные от fetch_data

        Returns:
            Optional[Dict[str, Any]]: Структурированные данные или None
        """
        if not raw_data or "html" not in raw_data:
            return None

        html = raw_data["html"]
        isbn = raw_data.get("isbn", "")
        resource_id = raw_data.get("resource_id", "")

        # Парсим HTML и извлекаем табличные данные
        table_data = self._extract_table_data(html, isbn)

        if table_data:
            table_data.update(
                {
                    "isbn": isbn,
                    "resource_id": resource_id,
                    "url": raw_data.get("url", ""),
                    "source": self.resource_config.get("name", resource_id),
                    "confidence": 0.8,  # Табличные данные могут быть менее структурированы
                }
            )

        return table_data

    def _extract_table_data(self, html: str, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Извлечение данных из HTML таблиц.

        Args:
            html: HTML страница
            isbn: ISBN для поиска

        Returns:
            Optional[Dict[str, Any]]: Извлеченные данные
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "lxml")

            # Ищем таблицы по селектору
            tables = soup.select(self.table_selector)
            if not tables:
                logger.debug(f"Таблицы не найдены по селектору: {self.table_selector}")
                return None

            # Пытаемся извлечь данные из каждой таблицы
            for table in tables:
                data = self._parse_table(table, isbn)
                if data:
                    return data

            return None

        except Exception as e:
            logger.error(f"Ошибка извлечения табличных данных: {e}")
            return None

    def _parse_table(self, table, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг конкретной таблицы.

        Args:
            table: BeautifulSoup объект таблицы
            isbn: ISBN для поиска

        Returns:
            Optional[Dict[str, Any]]: Извлеченные данные
        """
        # Извлекаем заголовки
        headers = self._extract_headers(table)
        if not headers:
            logger.debug("Заголовки таблицы не найдены")
            return None

        # Извлекаем строки данных
        data_rows = table.select(self.data_row_selector)
        if not data_rows:
            # Если нет tbody, берем все строки кроме заголовочных
            all_rows = table.find_all("tr")
            header_rows = table.select(self.header_row_selector)
            data_rows = [row for row in all_rows if row not in header_rows]

        # Ищем строку с нужным ISBN
        target_row = None
        for row in data_rows:
            row_text = row.get_text().lower()
            clean_isbn = isbn.replace("-", "").lower()

            # Проверяем, содержит ли строка ISBN
            if clean_isbn in row_text.replace("-", "").replace(" ", ""):
                target_row = row
                break

        if not target_row:
            logger.debug(f"Строка с ISBN {isbn} не найдена в таблице")
            return None

        # Извлекаем ячейки из целевой строки
        cells = target_row.select(self.cell_selector)
        if len(cells) != len(headers):
            logger.debug(
                f"Количество ячеек ({len(cells)}) не соответствует количеству заголовков ({len(headers)})"
            )
            # Все равно пытаемся извлечь данные

        # Сопоставляем ячейки с заголовками
        row_data = {}
        for i, header in enumerate(headers):
            if i < len(cells):
                cell_text = cells[i].get_text(strip=True)
                if cell_text:
                    row_data[header] = cell_text

        # Преобразуем данные в стандартный формат
        return self._map_table_data(row_data, headers)

    def _extract_headers(self, table) -> List[str]:
        """
        Извлечение заголовков таблицы.

        Args:
            table: BeautifulSoup объект таблицы

        Returns:
            List[str]: Список заголовков
        """
        headers = []

        # Пытаемся извлечь заголовки из thead
        header_rows = table.select(self.header_row_selector)
        if header_rows:
            for row in header_rows:
                cells = row.select(self.cell_selector)
                for cell in cells:
                    header_text = cell.get_text(strip=True)
                    if header_text:
                        headers.append(header_text)

        # Если заголовки не найдены, пытаемся найти первую строку как заголовки
        if not headers:
            first_row = table.find("tr")
            if first_row:
                cells = first_row.select(self.cell_selector)
                for cell in cells:
                    header_text = cell.get_text(strip=True)
                    if header_text:
                        headers.append(header_text)

        # Нормализуем заголовки
        normalized_headers = []
        for header in headers:
            normalized = self._normalize_header(header)
            if normalized:
                normalized_headers.append(normalized)

        return normalized_headers

    def _normalize_header(self, header: str) -> str:
        """
        Нормализация заголовка таблицы.

        Args:
            header: Исходный заголовок

        Returns:
            str: Нормализованный заголовок
        """
        # Приводим к нижнему регистру и удаляем лишние символы
        normalized = header.lower().strip()

        # Удаляем пунктуацию и лишние пробелы
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        # Русские синонимы для стандартных полей
        field_mapping = {
            "название": "title",
            "заголовок": "title",
            "наименование": "title",
            "автор": "author",
            "авторы": "authors",
            "составитель": "author",
            "редактор": "editor",
            "страниц": "pages",
            "количество страниц": "pages",
            "объем": "pages",
            "год": "year",
            "год издания": "year",
            "дата издания": "year",
            "издательство": "publisher",
            "издатель": "publisher",
            "isbn": "isbn",
            "индекс": "isbn",
            "код": "isbn",
        }

        # Проверяем синонимы
        for ru_field, en_field in field_mapping.items():
            if ru_field in normalized:
                return en_field

        # Если не нашли соответствие, возвращаем оригинал на английском
        en_mapping = {
            "title": "title",
            "author": "author",
            "authors": "authors",
            "pages": "pages",
            "year": "year",
            "publisher": "publisher",
            "isbn": "isbn",
        }

        for en_field in en_mapping:
            if en_field in normalized:
                return en_field

        # Возвращаем нормализованный заголовок
        return normalized.replace(" ", "_")

    def _map_table_data(
        self, row_data: Dict[str, str], headers: List[str]
    ) -> Dict[str, Any]:
        """
        Преобразование данных таблицы в стандартный формат.

        Args:
            row_data: Данные строки таблицы
            headers: Заголовки таблицы

        Returns:
            Dict[str, Any]: Стандартизированные данные
        """
        result = {}

        # Используем маппинг из конфигурации, если задан
        if self.field_mapping:
            for field, source in self.field_mapping.items():
                if isinstance(source, str) and source in row_data:
                    result[field] = row_data[source]
                elif isinstance(source, list):
                    for src in source:
                        if src in row_data:
                            result[field] = row_data[src]
                            break

        # Если маппинг не задан или не сработал, пытаемся определить автоматически
        if not result:
            # Ищем заголовки, соответствующие стандартным полям
            for header, value in row_data.items():
                field = self._determine_field_from_header(header)
                if field and value:
                    result[field] = value

        # Обрабатываем специальные случаи
        result = self._process_special_cases(result, row_data)

        return result

    def _determine_field_from_header(self, header: str) -> Optional[str]:
        """
        Определение поля по заголовку таблицы.

        Args:
            header: Заголовок таблицы

        Returns:
            Optional[str]: Имя поля или None
        """
        header_lower = header.lower()

        # Маппинг заголовков на поля
        mapping = {
            "title": ["title", "name", "название", "заголовок", "наименование"],
            "authors": ["author", "authors", "автор", "авторы", "составитель"],
            "pages": ["pages", "page", "страниц", "количество страниц", "объем"],
            "year": ["year", "год", "год издания", "дата издания", "publication"],
            "publisher": ["publisher", "издательство", "издатель", "publishing"],
            "isbn": ["isbn", "индекс", "код", "номер"],
        }

        for field, patterns in mapping.items():
            for pattern in patterns:
                if pattern in header_lower:
                    return field

        return None

    def _process_special_cases(
        self, result: Dict[str, Any], row_data: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Обработка специальных случаев данных.

        Args:
            result: Текущие данные
            row_data: Исходные данные строки

        Returns:
            Dict[str, Any]: Обработанные данные
        """
        # Обработка авторов
        if "authors" in result and isinstance(result["authors"], str):
            authors_str = result["authors"]
            # Разделяем авторов по запятым, точкам с запятой или "и"
            authors = re.split(r"[,;]|\s+и\s+", authors_str)
            authors = [author.strip() for author in authors if author.strip()]
            result["authors"] = authors

        # Обработка года издания
        if "year" in result and isinstance(result["year"], str):
            year_str = result["year"]
            # Извлекаем год из строки
            year_match = re.search(r"\d{4}", year_str)
            if year_match:
                result["year"] = year_match.group()

        # Обработка количества страниц
        if "pages" in result and isinstance(result["pages"], str):
            pages_str = result["pages"]
            # Извлекаем число из строки
            pages_match = re.search(r"\d+", pages_str)
            if pages_match:
                result["pages"] = pages_match.group()

        return result

    async def close(self):
        """Закрытие ресурсов."""
        pass
