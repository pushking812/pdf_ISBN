"""
Обработчик JSON-LD ресурсов.

Обрабатывает ресурсы с данными в формате JSON-LD (структурированные данные).
"""

import json
import re
from typing import Dict, Any, Optional, List
import logging

from .base import ResourceHandler

logger = logging.getLogger(__name__)


class JsonLdResourceHandler(ResourceHandler):
    """Обработчик JSON-LD ресурсов."""

    def __init__(self, resource_config: Dict[str, Any]):
        super().__init__(resource_config)
        self.jsonld_selector = resource_config.get(
            "jsonld_selector", 'script[type="application/ld+json"]'
        )

    async def fetch_data(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Получение данных с JSON-LD ресурса.

        Args:
            isbn: ISBN для поиска

        Returns:
            Optional[Dict[str, Any]]: Сырые данные или None
        """
        # JSON-LD обычно встроен в HTML, поэтому используем веб-обработчик
        # для получения HTML, а затем извлекаем JSON-LD
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
        Парсинг JSON-LD данных.

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

        # Извлекаем JSON-LD из HTML
        jsonld_data = self._extract_jsonld(html)
        if not jsonld_data:
            logger.debug(f"JSON-LD не найден для ресурса {resource_id}")
            return None

        # Парсим JSON-LD
        parsed_data = self._parse_jsonld(jsonld_data, isbn)

        if parsed_data:
            parsed_data.update(
                {
                    "isbn": isbn,
                    "resource_id": resource_id,
                    "url": raw_data.get("url", ""),
                    "source": self.resource_config.get("name", resource_id),
                    "confidence": 0.9,  # JSON-LD данные обычно достоверны
                }
            )

        return parsed_data

    def _extract_jsonld(self, html: str) -> Optional[List[Dict]]:
        """
        Извлечение JSON-LD из HTML.

        Args:
            html: HTML страница

        Returns:
            Optional[List[Dict]]: Список JSON-LD объектов или None
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "lxml")
            jsonld_scripts = soup.find_all("script", type="application/ld+json")

            if not jsonld_scripts:
                # Пытаемся найти JSON-LD в других script тегах
                all_scripts = soup.find_all("script")
                jsonld_scripts = []
                for script in all_scripts:
                    if script.string and "application/ld+json" in str(script):
                        jsonld_scripts.append(script)

            jsonld_objects = []
            for script in jsonld_scripts:
                try:
                    json_text = script.string.strip()
                    # Очищаем JSON от возможных комментариев и лишних символов
                    json_text = re.sub(r"/\*.*?\*/", "", json_text, flags=re.DOTALL)
                    json_text = re.sub(r"//.*$", "", json_text, flags=re.MULTILINE)

                    data = json.loads(json_text)
                    if isinstance(data, list):
                        jsonld_objects.extend(data)
                    else:
                        jsonld_objects.append(data)
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.debug(f"Ошибка парсинга JSON-LD: {e}")
                    continue

            return jsonld_objects if jsonld_objects else None

        except Exception as e:
            logger.error(f"Ошибка извлечения JSON-LD: {e}")
            return None

    def _parse_jsonld(
        self, jsonld_objects: List[Dict], isbn: str
    ) -> Optional[Dict[str, Any]]:
        """
        Парсинг JSON-LD объектов.

        Args:
            jsonld_objects: Список JSON-LD объектов
            isbn: ISBN для поиска (для фильтрации)

        Returns:
            Optional[Dict[str, Any]]: Структурированные данные
        """
        result = {}

        for obj in jsonld_objects:
            # Проверяем тип объекта
            obj_type = obj.get("@type", "")
            if not obj_type:
                continue

            # Ищем объекты типа Book, Product, CreativeWork
            book_types = ["Book", "Product", "CreativeWork", "PublicationVolume"]
            if not any(
                book_type.lower() in str(obj_type).lower() for book_type in book_types
            ):
                continue

            # Извлекаем данные книги
            book_data = self._extract_book_data_from_jsonld(obj, isbn)
            if book_data:
                # Объединяем с существующим результатом
                for key, value in book_data.items():
                    if value and (key not in result or not result[key]):
                        result[key] = value

        return result if result else None

    def _extract_book_data_from_jsonld(
        self, jsonld_obj: Dict, isbn: str
    ) -> Dict[str, Any]:
        """
        Извлечение данных книги из JSON-LD объекта.

        Args:
            jsonld_obj: JSON-LD объект
            isbn: ISBN для проверки

        Returns:
            Dict[str, Any]: Извлеченные данные книги
        """
        data = {}

        # Извлекаем ISBN для проверки
        jsonld_isbn = self._extract_isbn_from_jsonld(jsonld_obj)
        if (
            jsonld_isbn
            and isbn
            and jsonld_isbn.replace("-", "") != isbn.replace("-", "")
        ):
            # ISBN не совпадает, пропускаем
            return data

        # Извлекаем заголовок
        data["title"] = self._extract_field(jsonld_obj, ["name", "title", "headline"])

        # Извлекаем авторов
        authors = self._extract_authors_from_jsonld(jsonld_obj)
        if authors:
            data["authors"] = authors

        # Извлекаем количество страниц
        pages = self._extract_field(jsonld_obj, ["numberOfPages", "pageCount", "pages"])
        if pages:
            data["pages"] = str(pages)

        # Извлекаем год издания
        year = self._extract_year_from_jsonld(jsonld_obj)
        if year:
            data["year"] = str(year)

        # Извлекаем издателя
        publisher = self._extract_field(jsonld_obj, ["publisher", "publisher.name"])
        if publisher:
            data["publisher"] = publisher

        # Извлекаем описание
        description = self._extract_field(jsonld_obj, ["description", "abstract"])
        if description:
            data["description"] = description

        return data

    def _extract_isbn_from_jsonld(self, jsonld_obj: Dict) -> Optional[str]:
        """Извлечение ISBN из JSON-LD объекта."""
        isbn = self._extract_field(jsonld_obj, ["isbn", "productID", "sku"])
        if isbn:
            # Очищаем ISBN
            isbn = re.sub(r"[^0-9X]", "", str(isbn).upper())
            if len(isbn) in [10, 13]:
                return isbn

        # Проверяем в identifier
        identifier = jsonld_obj.get("identifier")
        if identifier:
            if (
                isinstance(identifier, dict)
                and identifier.get("@type") == "PropertyValue"
            ):
                value = identifier.get("value")
                if value and re.search(r"(\d{9}[\dX]|\d{13})", str(value)):
                    return re.search(r"(\d{9}[\dX]|\d{13})", str(value)).group()
            elif isinstance(identifier, str) and re.search(
                r"(\d{9}[\dX]|\d{13})", identifier
            ):
                return re.search(r"(\d{9}[\dX]|\d{13})", identifier).group()

        return None

    def _extract_authors_from_jsonld(self, jsonld_obj: Dict) -> List[str]:
        """Извлечение авторов из JSON-LD объекта."""
        authors = []

        # Пытаемся извлечь авторов разными способами
        author_field = jsonld_obj.get("author")
        if author_field:
            if isinstance(author_field, dict):
                name = author_field.get("name")
                if name:
                    authors.append(str(name))
            elif isinstance(author_field, list):
                for author in author_field:
                    if isinstance(author, dict):
                        name = author.get("name")
                        if name:
                            authors.append(str(name))
                    elif isinstance(author, str):
                        authors.append(author)
            elif isinstance(author_field, str):
                authors.append(author_field)

        # Проверяем creator
        if not authors:
            creator_field = jsonld_obj.get("creator")
            if creator_field:
                if isinstance(creator_field, dict):
                    name = creator_field.get("name")
                    if name:
                        authors.append(str(name))
                elif isinstance(creator_field, list):
                    for creator in creator_field:
                        if isinstance(creator, dict):
                            name = creator.get("name")
                            if name:
                                authors.append(str(name))
                        elif isinstance(creator, str):
                            authors.append(creator)
                elif isinstance(creator_field, str):
                    authors.append(creator_field)

        return authors

    def _extract_year_from_jsonld(self, jsonld_obj: Dict) -> Optional[int]:
        """Извлечение года издания из JSON-LD объекта."""
        # Пытаемся извлечь дату публикации
        date_field = self._extract_field(
            jsonld_obj, ["datePublished", "publicationDate", "copyrightYear"]
        )
        if date_field:
            # Пытаемся извлечь год из строки даты
            if isinstance(date_field, str):
                year_match = re.search(r"\d{4}", date_field)
                if year_match:
                    try:
                        return int(year_match.group())
                    except ValueError:
                        pass

        # Проверяем copyrightYear
        copyright_year = jsonld_obj.get("copyrightYear")
        if copyright_year:
            try:
                return int(copyright_year)
            except (ValueError, TypeError):
                pass

        return None

    def _extract_field(self, obj: Dict, field_names: List[str]) -> Optional[Any]:
        """
        Извлечение поля из объекта по списку возможных имен.

        Args:
            obj: JSON объект
            field_names: Список возможных имен поля

        Returns:
            Optional[Any]: Значение поля или None
        """
        for field_name in field_names:
            if "." in field_name:
                # Вложенное поле
                keys = field_name.split(".")
                value = obj
                for key in keys:
                    if isinstance(value, dict) and key in value:
                        value = value[key]
                    else:
                        value = None
                        break
                if value is not None:
                    return value
            elif field_name in obj:
                return obj[field_name]

        return None

    async def close(self):
        """Закрытие ресурсов."""
        pass
