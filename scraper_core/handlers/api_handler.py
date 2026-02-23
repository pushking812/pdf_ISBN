"""
Обработчик API-ресурсов.

Обрабатывает ресурсы, предоставляющие данные через REST API.
"""

import asyncio
import aiohttp
from typing import Dict, Any, Optional
import logging
import json

from .base import ResourceHandler

logger = logging.getLogger(__name__)


class ApiResourceHandler(ResourceHandler):
    """Обработчик API-ресурсов."""

    def __init__(self, resource_config: Dict[str, Any]):
        super().__init__(resource_config)
        self.api_endpoint = resource_config.get("api_endpoint", "")
        self.api_key = resource_config.get("api_key", "")
        self.headers = resource_config.get("headers", {})
        self.timeout = resource_config.get("timeout", 30)

        # Настройка заголовков по умолчанию
        if "User-Agent" not in self.headers:
            self.headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

        if self.api_key and "Authorization" not in self.headers:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    async def fetch_data(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Получение данных через API.

        Args:
            isbn: ISBN для поиска

        Returns:
            Optional[Dict[str, Any]]: Ответ API или None
        """
        if not self.api_endpoint:
            logger.error(f"API endpoint не указан для ресурса: {self.resource_id}")
            return None

        clean_isbn = isbn.replace("-", "").strip()

        # Формирование URL запроса
        url = self.api_endpoint.format(isbn=clean_isbn)

        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, timeout=self.timeout) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")

                        if "application/json" in content_type:
                            data = await response.json()
                        else:
                            text = await response.text()
                            # Пытаемся распарсить как JSON, даже если content-type не указан
                            try:
                                data = json.loads(text)
                            except json.JSONDecodeError:
                                data = {"raw_text": text}

                        return {
                            "api_response": data,
                            "status_code": response.status,
                            "url": str(response.url),
                            "isbn": isbn,
                            "resource_id": self.resource_id,
                        }
                    else:
                        logger.warning(
                            f"API вернул статус {response.status} для ISBN {isbn}"
                        )
                        return {
                            "api_response": None,
                            "status_code": response.status,
                            "url": str(response.url),
                            "isbn": isbn,
                            "resource_id": self.resource_id,
                            "error": f"HTTP {response.status}",
                        }
        except asyncio.TimeoutError:
            logger.error(f"Таймаут API запроса для ISBN {isbn}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка клиента API для ISBN {isbn}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка API для ISBN {isbn}: {e}")
            return None

    def parse_data(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Парсинг ответа API.

        Args:
            raw_data: Сырые данные от fetch_data

        Returns:
            Optional[Dict[str, Any]]: Структурированные данные или None
        """
        if not raw_data or "api_response" not in raw_data:
            return None

        api_response = raw_data["api_response"]
        status_code = raw_data.get("status_code", 0)

        if status_code != 200 or not api_response:
            return None

        # Получаем маппинг полей из конфигурации
        field_mapping = self.resource_config.get("field_mapping", {})

        # Функция для извлечения значения по пути
        def get_value(data, path):
            if not path:
                return None

            if isinstance(path, str):
                keys = path.split(".")
            elif isinstance(path, list):
                keys = path
            else:
                return None

            current = data
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                elif (
                    isinstance(current, list)
                    and key.isdigit()
                    and int(key) < len(current)
                ):
                    current = current[int(key)]
                else:
                    return None

            return current

        # Извлекаем данные по маппингу
        result = {}
        for field, path in field_mapping.items():
            value = get_value(api_response, path)
            if value is not None:
                result[field] = value

        # Если маппинг не задан, пытаемся извлечь стандартные поля
        if not result:
            result = self._extract_standard_fields(api_response)

        # Добавляем метаданные
        if result:
            result.update(
                {
                    "isbn": raw_data.get("isbn", ""),
                    "resource_id": self.resource_id,
                    "url": raw_data.get("url", ""),
                    "source": self.resource_config.get("name", self.resource_id),
                    "confidence": 1.0,  # API данные обычно достоверны
                }
            )

        return result if result else None

    def _extract_standard_fields(self, api_response: Any) -> Dict[str, Any]:
        """
        Извлечение стандартных полей из ответа API.

        Args:
            api_response: Ответ API

        Returns:
            Dict[str, Any]: Извлеченные поля
        """
        result = {}

        # Пытаемся найти стандартные поля в ответе
        if isinstance(api_response, dict):
            # Google Books API формат
            if "volumeInfo" in api_response:
                volume_info = api_response["volumeInfo"]
                result["title"] = volume_info.get("title", "")
                result["authors"] = volume_info.get("authors", [])
                result["pages"] = volume_info.get("pageCount")
                result["year"] = (
                    volume_info.get("publishedDate", "").split("-")[0]
                    if volume_info.get("publishedDate")
                    else None
                )

            # Open Library API формат
            elif "docs" in api_response and api_response["docs"]:
                doc = api_response["docs"][0]
                result["title"] = doc.get("title", "")
                result["authors"] = [
                    author.get("name", "") for author in doc.get("author_name", [])
                ]
                result["pages"] = doc.get("number_of_pages_median")
                result["year"] = doc.get("first_publish_year")

            # Прямые поля
            else:
                result["title"] = api_response.get("title") or api_response.get("name")
                result["authors"] = (
                    api_response.get("authors") or api_response.get("author") or []
                )
                if isinstance(result["authors"], str):
                    result["authors"] = [result["authors"]]
                result["pages"] = api_response.get("pages") or api_response.get(
                    "pageCount"
                )
                result["year"] = (
                    api_response.get("year")
                    or api_response.get("publishedDate")
                    or api_response.get("publication_year")
                )

        return result

    async def close(self):
        """Закрытие ресурсов (для API обычно не требуется)."""
        pass
