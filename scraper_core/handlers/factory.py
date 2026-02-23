"""
Фабрика обработчиков ресурсов.

Создает обработчики на основе типа ресурса.
"""

from typing import Dict, Any, Optional, Type
import logging
from .base import ResourceHandler

logger = logging.getLogger(__name__)


class ResourceHandlerFactory:
    """Фабрика обработчиков ресурсов."""

    # Регистр обработчиков по типу ресурса
    _handler_registry: Dict[str, Type[ResourceHandler]] = {}

    @classmethod
    def register_handler(cls, resource_type: str, handler_class: Type[ResourceHandler]):
        """
        Регистрация обработчика для типа ресурса.

        Args:
            resource_type: Тип ресурса (web, api, json_ld, table)
            handler_class: Класс обработчика
        """
        cls._handler_registry[resource_type] = handler_class
        logger.debug(f"Зарегистрирован обработчик для типа ресурса: {resource_type}")

    @classmethod
    def create_handler(
        cls, resource_config: Dict[str, Any], retry_handler=None
    ) -> Optional[ResourceHandler]:
        """
        Создание обработчика на основе конфигурации ресурса.

        Args:
            resource_config: Конфигурация ресурса
            retry_handler: Обработчик повторных попыток (опционально)

        Returns:
            Optional[ResourceHandler]: Обработчик ресурса или None
        """
        resource_type = resource_config.get("type", "web")
        resource_id = resource_config.get("id", "unknown")

        # Получаем класс обработчика из регистра
        handler_class = cls._handler_registry.get(resource_type)

        if not handler_class:
            logger.warning(f"Не найден обработчик для типа ресурса: {resource_type}")
            # Используем базовый обработчик по умолчанию
            from .web_handler import WebResourceHandler

            handler_class = WebResourceHandler

        try:
            # Создаем экземпляр обработчика с передачей retry_handler
            # Проверяем, поддерживает ли обработчик параметр retry_handler
            import inspect

            sig = inspect.signature(handler_class.__init__)
            params = list(sig.parameters.keys())

            if "retry_handler" in params:
                handler = handler_class(resource_config, retry_handler=retry_handler)
            else:
                handler = handler_class(resource_config)

            logger.debug(
                f"Создан обработчик для ресурса: {resource_id} (тип: {resource_type})"
            )
            return handler
        except Exception as e:
            logger.error(f"Ошибка создания обработчика для ресурса {resource_id}: {e}")
            return None

    @classmethod
    def get_available_resource_types(cls) -> list[str]:
        """
        Получение списка доступных типов ресурсов.

        Returns:
            list[str]: Список типов ресурсов
        """
        return list(cls._handler_registry.keys())


# Импортируем и регистрируем обработчики
try:
    from .web_handler import WebResourceHandler

    ResourceHandlerFactory.register_handler("web", WebResourceHandler)
    ResourceHandlerFactory.register_handler("selenium", WebResourceHandler)
except ImportError:
    logger.warning("WebResourceHandler не найден, регистрация пропущена")

try:
    from .api_handler import ApiResourceHandler

    ResourceHandlerFactory.register_handler("api", ApiResourceHandler)
    ResourceHandlerFactory.register_handler("rest", ApiResourceHandler)
except ImportError:
    logger.warning("ApiResourceHandler не найден, регистрация пропущена")

try:
    from .jsonld_handler import JsonLdResourceHandler

    ResourceHandlerFactory.register_handler("json_ld", JsonLdResourceHandler)
    ResourceHandlerFactory.register_handler("json", JsonLdResourceHandler)
except ImportError:
    logger.warning("JsonLdResourceHandler не найден, регистрация пропущена")

try:
    from .table_handler import TableResourceHandler

    ResourceHandlerFactory.register_handler("table", TableResourceHandler)
    ResourceHandlerFactory.register_handler("tabular", TableResourceHandler)
except ImportError:
    logger.warning("TableResourceHandler не найден, регистрация пропущена")
