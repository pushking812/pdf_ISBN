"""
Сборщик ссылок для извлечения и валидации URL продуктов.

LinkCollector отвечает за:
1. Извлечение ссылок на продукты со страниц поиска
2. Фильтрацию дубликатов ссылок
3. Валидацию URL (преобразование относительных в абсолютные)
4. Кеширование ссылок для повышения производительности
"""

import hashlib
import logging
import urllib.parse
from typing import Any, Dict, List, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LinkCacheEntry:
    """Запись в кеше ссылок."""

    url: str
    resource_id: str
    isbn: str
    created_at: datetime
    expires_at: datetime


class LinkCollector:
    """Сборщик ссылок для извлечения URL продуктов."""

    def __init__(self, cache_ttl_seconds: int = 3600):
        """
        Инициализация сборщика ссылок.

        Args:
            cache_ttl_seconds: Время жизни кеша ссылок в секундах
        """
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.link_cache: Dict[str, LinkCacheEntry] = {}
        self.seen_urls: Set[str] = set()

    def _normalize_url(self, url: str, base_url: str) -> str:
        """
        Нормализация URL: преобразование относительного в абсолютный.

        Args:
            url: URL для нормализации
            base_url: Базовый URL для разрешения относительных путей

        Returns:
            Нормализованный абсолютный URL
        """
        if not url:
            return ""

        # Если URL уже абсолютный
        if url.startswith(("http://", "https://")):
            return url

        # Если URL начинается с //
        if url.startswith("//"):
            parsed_base = urllib.parse.urlparse(base_url)
            return f"{parsed_base.scheme}:{url}"

        # Если URL начинается с /
        if url.startswith("/"):
            parsed_base = urllib.parse.urlparse(base_url)
            return f"{parsed_base.scheme}://{parsed_base.netloc}{url}"

        # Относительный URL без ведущего слеша
        return urllib.parse.urljoin(base_url, url)

    def _is_valid_url(self, url: str) -> bool:
        """
        Проверка валидности URL.

        Args:
            url: URL для проверки

        Returns:
            True если URL валиден, иначе False
        """
        if not url or not isinstance(url, str):
            return False

        try:
            parsed = urllib.parse.urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False

    def _generate_cache_key(self, isbn: str, resource_id: str) -> str:
        """
        Генерация ключа кеша для ISBN и ресурса.

        Args:
            isbn: ISBN книги
            resource_id: Идентификатор ресурса

        Returns:
            Ключ кеша
        """
        key_data = f"{isbn}:{resource_id}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _clean_cache(self):
        """Очистка устаревших записей из кеша."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.link_cache.items() if entry.expires_at < now
        ]

        for key in expired_keys:
            del self.link_cache[key]

        logger.debug(f"Очищен кеш ссылок: удалено {len(expired_keys)} записей")

    async def collect_links(
        self, isbn: str, resource_config: Dict[str, Any], web_handler: Any
    ) -> List[str]:
        """
        Сбор ссылок на продукты для заданного ISBN и ресурса.

        Args:
            isbn: ISBN для поиска
            resource_config: Конфигурация ресурса
            web_handler: Экземпляр WebResourceHandler для загрузки страниц

        Returns:
            Список найденных ссылок на продукты
        """
        resource_id = resource_config.get("id", "unknown")
        cache_key = self._generate_cache_key(isbn, resource_id)

        # Проверка кеша
        self._clean_cache()
        if cache_key in self.link_cache:
            entry = self.link_cache[cache_key]
            logger.debug(f"Найдены ссылки в кеше для ISBN {isbn}, ресурс {resource_id}")
            return [entry.url] if entry.url else []

        clean_isbn = isbn.replace("-", "").strip()
        search_url = resource_config.get("search_url_template", "").format(
            isbn=clean_isbn
        )

        if not search_url:
            logger.error(f"URL шаблон не найден для ресурса: {resource_id}")
            self._cache_result(cache_key, isbn, resource_id, [])
            return []

        logger.info(f"Поиск ссылок для ISBN {isbn} на ресурсе {resource_id}")

        try:
            # Загрузка страницы поиска
            page_content = await web_handler.fetch_page(search_url)
            if not page_content:
                logger.warning(f"Не удалось загрузить страницу поиска для ISBN {isbn}")
                self._cache_result(cache_key, isbn, resource_id, [])
                return []

            # Проверка на страницу "ничего не найдено"
            if await self._check_no_results(page_content, resource_config):
                logger.debug(
                    f"Книга не найдена для ISBN {isbn} на ресурсе {resource_id}"
                )
                self._cache_result(cache_key, isbn, resource_id, [])
                return []

            # Извлечение ссылок
            links = await self._extract_links(page_content, search_url, resource_config)

            # Фильтрация дубликатов и валидация
            unique_links = self._filter_and_validate_links(links, search_url)

            logger.info(
                f"Найдено {len(unique_links)} ссылок для ISBN {isbn} "
                f"на ресурсе {resource_id}"
            )

            # Кеширование результатов
            self._cache_result(cache_key, isbn, resource_id, unique_links)

            return unique_links

        except Exception as e:
            logger.error(f"Ошибка при сборе ссылок для ISBN {isbn}: {e}")
            self._cache_result(cache_key, isbn, resource_id, [])
            return []

    async def _check_no_results(
        self, page_content: str, resource_config: Dict[str, Any]
    ) -> bool:
        """
        Проверка на страницу 'ничего не найдено'.

        Args:
            page_content: Содержимое страницы
            resource_config: Конфигурация ресурса

        Returns:
            True если страница указывает на отсутствие результатов
        """
        page_text = page_content.lower()
        no_product_phrases = resource_config.get("no_product_phrases", [])

        for phrase in no_product_phrases:
            if phrase and phrase.lower() in page_text:
                return True

        return False

    async def _extract_links(
        self, page_content: str, base_url: str, resource_config: Dict[str, Any]
    ) -> List[str]:
        """
        Извлечение ссылок из содержимого страницы.

        Args:
            page_content: HTML содержимое страницы
            base_url: Базовый URL для разрешения относительных путей
            resource_config: Конфигурация ресурса

        Returns:
            Список найденных ссылок
        """
        links = []
        selectors = resource_config.get("product_link_selectors", [])

        if not selectors:
            logger.warning(
                f"Нет селекторов для извлечения ссылок у ресурса {resource_config.get('id')}"
            )
            return []

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(page_content, "lxml")

            for selector in selectors:
                elements = soup.select(selector)
                for element in elements:
                    href = element.get("href")
                    if href:
                        links.append(href)

                if elements:
                    logger.debug(
                        f"Селектор '{selector}' нашел {len(elements)} элементов"
                    )

        except ImportError:
            logger.warning("BeautifulSoup не установлен, используем простой парсинг")
            # Простой парсинг без BeautifulSoup (резервный вариант)
            import re

            for selector in selectors:
                # Преобразуем CSS селектор в простой regex для поиска href
                # Это упрощенная реализация, в production нужен более надежный подход
                pattern = r'href="([^"]*)"'
                matches = re.findall(pattern, page_content)
                links.extend(matches)

        return links

    def _filter_and_validate_links(self, links: List[str], base_url: str) -> List[str]:
        """
        Фильтрация дубликатов и валидация ссылок.

        Args:
            links: Список сырых ссылок
            base_url: Базовый URL для нормализации

        Returns:
            Список уникальных валидных ссылок
        """
        unique_links = []
        seen = set()

        for link in links:
            # Нормализация URL
            normalized = self._normalize_url(link, base_url)

            # Проверка валидности
            if not self._is_valid_url(normalized):
                continue

            # Проверка на дубликат
            if normalized in seen:
                continue

            seen.add(normalized)
            unique_links.append(normalized)

        return unique_links

    def _cache_result(
        self, cache_key: str, isbn: str, resource_id: str, links: List[str]
    ):
        """
        Кеширование результатов поиска ссылок.

        Args:
            cache_key: Ключ кеша
            isbn: ISBN книги
            resource_id: Идентификатор ресурса
            links: Список найденных ссылок
        """
        now = datetime.now()
        expires_at = now + self.cache_ttl

        # Для простоты кешируем только первую ссылку
        # В будущем можно расширить для хранения всех ссылок
        primary_link = links[0] if links else ""

        entry = LinkCacheEntry(
            url=primary_link,
            resource_id=resource_id,
            isbn=isbn,
            created_at=now,
            expires_at=expires_at,
        )

        self.link_cache[cache_key] = entry
        logger.debug(f"Результаты кешированы для ISBN {isbn}, ресурс {resource_id}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики сборщика ссылок.

        Returns:
            Словарь со статистикой
        """
        return {
            "cache_size": len(self.link_cache),
            "seen_urls_count": len(self.seen_urls),
            "cache_hit_rate": self._calculate_cache_hit_rate(),
        }

    def _calculate_cache_hit_rate(self) -> float:
        """
        Расчет коэффициента попаданий в кеш.

        Returns:
            Коэффициент попаданий (0.0 - 1.0)
        """
        # Временная реализация, в production нужно отслеживать фактические попадания
        return 0.0

    async def clear_cache(self):
        """Очистка всего кеша ссылок."""
        self.link_cache.clear()
        self.seen_urls.clear()
        logger.info("Кеш ссылок полностью очищен")
