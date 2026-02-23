"""
Тесты для LinkCollector.
"""

import pytest
from unittest.mock import AsyncMock, patch
from scraper_core.orchestrator.links import LinkCollector


class TestLinkCollector:
    """Тесты для класса LinkCollector."""

    def test_init(self):
        """Тест инициализации LinkCollector."""
        collector = LinkCollector(cache_ttl_seconds=1800)
        assert collector.cache_ttl.total_seconds() == 1800
        assert len(collector.link_cache) == 0
        assert len(collector.seen_urls) == 0

    def test_normalize_url(self):
        """Тест нормализации URL."""
        collector = LinkCollector()
        base_url = "https://example.com"

        # Абсолютный URL
        assert (
            collector._normalize_url("https://example.com/book", base_url)
            == "https://example.com/book"
        )

        # Относительный URL с ведущим слешем
        assert (
            collector._normalize_url("/book/123", base_url)
            == "https://example.com/book/123"
        )

        # Относительный URL без ведущего слеша
        assert (
            collector._normalize_url("book/123", base_url)
            == "https://example.com/book/123"
        )

        # URL с //
        assert (
            collector._normalize_url("//cdn.example.com/image.jpg", base_url)
            == "https://cdn.example.com/image.jpg"
        )

        # Пустой URL
        assert collector._normalize_url("", base_url) == ""

    def test_is_valid_url(self):
        """Тест проверки валидности URL."""
        collector = LinkCollector()

        # Валидные URL
        assert collector._is_valid_url("https://example.com/book") is True
        assert collector._is_valid_url("http://example.com") is True
        assert collector._is_valid_url("https://sub.example.com/path?query=1") is True

        # Невалидные URL
        assert collector._is_valid_url("") is False
        assert collector._is_valid_url(None) is False
        assert collector._is_valid_url("/relative/path") is False
        assert collector._is_valid_url("invalid") is False

    def test_generate_cache_key(self):
        """Тест генерации ключа кеша."""
        collector = LinkCollector()
        key1 = collector._generate_cache_key("9781234567890", "book-ru")
        key2 = collector._generate_cache_key("9781234567890", "book-ru")
        key3 = collector._generate_cache_key("9780987654321", "book-ru")

        # Ключи должны быть одинаковыми для одинаковых входных данных
        assert key1 == key2
        # Ключи должны быть разными для разных ISBN
        assert key1 != key3

    @pytest.mark.asyncio
    async def test_collect_links_with_cache(self):
        """Тест сбора ссылок с использованием кеша."""
        collector = LinkCollector(cache_ttl_seconds=3600)

        # Мокаем web_handler
        mock_web_handler = AsyncMock()

        # Первый вызов - кеш пуст
        with patch.object(
            collector, "_extract_links", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = ["https://example.com/book/1"]
            links = await collector.collect_links(
                "9781234567890",
                {
                    "id": "test-resource",
                    "search_url_template": "https://example.com/search?q={isbn}",
                },
                mock_web_handler,
            )

            assert len(links) == 1
            assert links[0] == "https://example.com/book/1"
            mock_extract.assert_called_once()

        # Второй вызов - должен использовать кеш
        with patch.object(
            collector, "_extract_links", new_callable=AsyncMock
        ) as mock_extract:
            links = await collector.collect_links(
                "9781234567890",
                {
                    "id": "test-resource",
                    "search_url_template": "https://example.com/search?q={isbn}",
                },
                mock_web_handler,
            )

            # Должен вернуть результат из кеша, не вызывая extract_links
            mock_extract.assert_not_called()
            assert len(links) == 1
            assert links[0] == "https://example.com/book/1"

    @pytest.mark.asyncio
    async def test_collect_links_no_results(self):
        """Тест сбора ссылок, когда книга не найдена."""
        collector = LinkCollector()

        mock_web_handler = AsyncMock()
        mock_web_handler.fetch_page.return_value = "<html>Ничего не найдено</html>"

        resource_config = {
            "id": "test-resource",
            "search_url_template": "https://example.com/search?q={isbn}",
            "no_product_phrases": ["Ничего не найдено"],
        }

        links = await collector.collect_links(
            "9781234567890", resource_config, mock_web_handler
        )

        assert len(links) == 0

    @pytest.mark.asyncio
    async def test_collect_links_extraction(self):
        """Тест извлечения ссылок из HTML."""
        collector = LinkCollector()

        html_content = """
        <html>
            <body>
                <a href="/book/1" class="product-link">Book 1</a>
                <a href="/book/2" class="product-link">Book 2</a>
                <a href="https://external.com/book/3">Book 3</a>
            </body>
        </html>
        """

        resource_config = {
            "id": "test-resource",
            "product_link_selectors": [".product-link", "a[href*='book']"],
        }

        links = await collector._extract_links(
            html_content, "https://example.com", resource_config
        )

        # Должны быть найдены все ссылки
        assert "/book/1" in links
        assert "/book/2" in links
        assert "https://external.com/book/3" in links

    def test_filter_and_validate_links(self):
        """Тест фильтрации и валидации ссылок."""
        collector = LinkCollector()

        raw_links = [
            "/book/1",
            "/book/1",  # Дубликат
            "https://example.com/book/2",
            "invalid-url",  # После нормализации станет https://example.com/invalid-url, который технически валиден
            "//cdn.example.com/image.jpg",
        ]

        filtered = collector._filter_and_validate_links(
            raw_links, "https://example.com"
        )

        # Должны остаться только уникальные валидные ссылки
        # invalid-url становится https://example.com/invalid-url, который проходит валидацию
        assert len(filtered) == 4
        assert "https://example.com/book/1" in filtered
        assert "https://example.com/book/2" in filtered
        assert "https://example.com/invalid-url" in filtered
        assert "https://cdn.example.com/image.jpg" in filtered

    def test_cache_cleanup(self):
        """Тест очистки устаревшего кеша."""
        collector = LinkCollector(
            cache_ttl_seconds=-1
        )  # Отрицательный TTL для немедленного устаревания

        # Добавляем запись в кеш
        collector._cache_result(
            "test-key", "9781234567890", "test-resource", ["https://example.com/book"]
        )

        # Очищаем кеш
        collector._clean_cache()

        # Кеш должен быть пустым
        assert len(collector.link_cache) == 0

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """Тест полной очистки кеша."""
        collector = LinkCollector()

        # Добавляем данные в кеш
        collector._cache_result("key1", "9781234567890", "res1", ["url1"])
        collector.seen_urls.add("url1")

        assert len(collector.link_cache) == 1
        assert len(collector.seen_urls) == 1

        # Очищаем кеш
        await collector.clear_cache()

        assert len(collector.link_cache) == 0
        assert len(collector.seen_urls) == 0

    def test_get_stats(self):
        """Тест получения статистики."""
        collector = LinkCollector()

        stats = collector.get_stats()

        assert "cache_size" in stats
        assert "seen_urls_count" in stats
        assert "cache_hit_rate" in stats
        assert stats["cache_size"] == 0
        assert stats["seen_urls_count"] == 0


class TestLinkCollectorIntegration:
    """Интеграционные тесты LinkCollector с WebResourceHandler."""

    @pytest.mark.asyncio
    async def test_integration_with_web_handler(self):
        """Тест интеграции LinkCollector с WebResourceHandler."""
        from scraper_core.handlers.web_handler import WebResourceHandler

        # Создаем мок конфигурации ресурса
        resource_config = {
            "id": "test-resource",
            "name": "Test Resource",
            "search_url_template": "https://example.com/search?q={isbn}",
            "product_link_selectors": [".product-link"],
            "use_selenium": False,
        }

        # Создаем экземпляры
        web_handler = WebResourceHandler(resource_config)
        link_collector = LinkCollector()

        # Мокаем fetch_page, чтобы не делать реальные HTTP-запросы
        with patch.object(
            web_handler, "fetch_page", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = """
                <html>
                    <a href="/book/123" class="product-link">Test Book</a>
                </html>
            """

            # Собираем ссылки
            links = await link_collector.collect_links(
                "9781234567890", resource_config, web_handler
            )

            # Проверяем результаты
            assert len(links) == 1
            assert links[0] == "https://example.com/book/123"

            # Проверяем, что fetch_page был вызван с правильным URL
            mock_fetch.assert_called_once_with(
                "https://example.com/search?q=9781234567890"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
