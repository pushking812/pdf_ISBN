"""
Парсеры для извлечения данных.

Модули:
- selector_client: Клиент для работы с селекторами (интеграция с debug_selectors)
- selector: Базовый клиент селекторов (устаревший, используйте selector_client)
"""

from .selector_client import SelectorClient
from .selector import SelectorClient as LegacySelectorClient

__all__ = ["SelectorClient", "LegacySelectorClient"]
