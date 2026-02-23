"""
Менеджер драйверов для централизованного управления WebDriver.

Предоставляет интерфейс для создания, переиспользования и очистки драйверов.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DriverType(Enum):
    """Типы драйверов."""

    CHROME = "chrome"
    FIREFOX = "firefox"
    REMOTE = "remote"


@dataclass
class DriverConfig:
    """Конфигурация драйвера."""

    driver_type: DriverType = DriverType.CHROME
    headless: bool = True
    page_load_strategy: str = "eager"
    page_load_timeout: int = 20
    window_size: tuple = (1920, 1080)
    options: Optional[Dict[str, Any]] = None
    capabilities: Optional[Dict[str, Any]] = None


class DriverManagerInterface(ABC):
    """Интерфейс менеджера драйверов."""

    @abstractmethod
    async def get_driver(self, driver_id: Optional[str] = None) -> Any:
        """
        Получение драйвера.

        Args:
            driver_id: Идентификатор драйвера (опционально)

        Returns:
            WebDriver экземпляр
        """
        pass

    @abstractmethod
    async def release_driver(
        self, driver: Any, driver_id: Optional[str] = None
    ) -> None:
        """
        Освобождение драйвера для повторного использования.

        Args:
            driver: WebDriver экземпляр
            driver_id: Идентификатор драйвера (опционально)
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Очистка всех драйверов."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики использования драйверов.

        Returns:
            Словарь со статистикой
        """
        pass


class SimpleDriverManager(DriverManagerInterface):
    """
    Простой менеджер драйверов с базовым пулом.

    Создает драйверы по требованию и управляет их жизненным циклом.
    """

    def __init__(self, config: Optional[DriverConfig] = None):
        """
        Инициализация менеджера драйверов.

        Args:
            config: Конфигурация драйверов (опционально)
        """
        self.config = config or DriverConfig()
        self._drivers: List[Any] = []
        self._available_drivers: List[Any] = []
        self._in_use_drivers: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._stats = {
            "created": 0,
            "reused": 0,
            "cleaned": 0,
            "max_concurrent": 0,
        }

        logger.info(
            f"SimpleDriverManager инициализирован с конфигурацией: {self.config}"
        )

    async def get_driver(self, driver_id: Optional[str] = None) -> Any:
        """
        Получение драйвера из пула или создание нового.

        Args:
            driver_id: Идентификатор драйвера (опционально)

        Returns:
            WebDriver экземпляр
        """
        async with self._lock:
            # Пытаемся взять доступный драйвер из пула
            if self._available_drivers:
                driver = self._available_drivers.pop()
                self._stats["reused"] += 1
                logger.debug("Переиспользован драйвер из пула")
            else:
                # Создаем новый драйвер
                driver = await self._create_driver()
                self._drivers.append(driver)
                self._stats["created"] += 1
                logger.debug("Создан новый драйвер")

            # Регистрируем драйвер как используемый
            driver_key = driver_id or f"driver_{id(driver)}"
            self._in_use_drivers[driver_key] = driver

            # Обновляем статистику максимального количества одновременных драйверов
            current_in_use = len(self._in_use_drivers)
            if current_in_use > self._stats["max_concurrent"]:
                self._stats["max_concurrent"] = current_in_use

            return driver

    async def release_driver(
        self, driver: Any, driver_id: Optional[str] = None
    ) -> None:
        """
        Освобождение драйвера для повторного использования.

        Args:
            driver: WebDriver экземпляр
            driver_id: Идентификатор драйвера (опционально)
        """
        async with self._lock:
            # Удаляем драйвер из списка используемых
            driver_key = driver_id or f"driver_{id(driver)}"
            if driver_key in self._in_use_drivers:
                del self._in_use_drivers[driver_key]

            # Проверяем состояние драйвера перед возвратом в пул
            try:
                # Простая проверка: если драйвер еще активен, возвращаем в пул
                if hasattr(driver, "current_url"):
                    self._available_drivers.append(driver)
                    logger.debug("Драйвер возвращен в пул")
                else:
                    # Драйвер невалиден, закрываем его
                    await self._close_driver(driver)
                    if driver in self._drivers:
                        self._drivers.remove(driver)
                    self._stats["cleaned"] += 1
                    logger.debug("Невалидный драйвер закрыт")
            except Exception as e:
                logger.error(f"Ошибка при проверке драйвера: {e}")
                # В случае ошибки закрываем драйвер
                await self._close_driver(driver)
                if driver in self._drivers:
                    self._drivers.remove(driver)
                self._stats["cleaned"] += 1

    async def cleanup(self) -> None:
        """Очистка всех драйверов."""
        async with self._lock:
            logger.info(f"Очистка {len(self._drivers)} драйверов")

            # Закрываем все драйверы
            for driver in self._drivers:
                await self._close_driver(driver)

            # Очищаем списки
            self._drivers.clear()
            self._available_drivers.clear()
            self._in_use_drivers.clear()

            self._stats["cleaned"] += len(self._drivers)
            logger.info("Все драйверы очищены")

    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики использования драйверов.

        Returns:
            Словарь со статистикой
        """
        return {
            **self._stats,
            "total_drivers": len(self._drivers),
            "available_drivers": len(self._available_drivers),
            "in_use_drivers": len(self._in_use_drivers),
            "config": {
                "driver_type": self.config.driver_type.value,
                "headless": self.config.headless,
                "page_load_strategy": self.config.page_load_strategy,
            },
        }

    async def _create_driver(self) -> Any:
        """
        Создание нового драйвера.

        Returns:
            WebDriver экземпляр

        Raises:
            ImportError: Если не установлены необходимые библиотеки
        """
        try:
            if self.config.driver_type == DriverType.CHROME:
                return await self._create_chrome_driver()
            else:
                # Для других типов драйверов используем заглушку
                raise NotImplementedError(
                    f"Тип драйвера {self.config.driver_type} пока не поддерживается"
                )
        except ImportError as e:
            logger.error(f"Ошибка импорта библиотеки драйвера: {e}")
            raise

    async def _create_chrome_driver(self) -> Any:
        """Создание Chrome драйвера."""
        try:
            import undetected_chromedriver as uc

            options = uc.ChromeOptions()

            # Базовые опции
            if self.config.headless:
                options.add_argument("--headless=new")

            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")

            # Стратегия загрузки страницы
            strategy = self.config.page_load_strategy.lower()
            if strategy not in ("normal", "eager", "none"):
                strategy = "eager"
            options.set_capability("pageLoadStrategy", strategy)

            # Дополнительные опции из конфигурации
            if self.config.options:
                for key, value in self.config.options.items():
                    if isinstance(value, bool) and value:
                        options.add_argument(f"--{key}")
                    elif isinstance(value, str):
                        options.add_argument(f"--{key}={value}")

            # Создание драйвера
            driver = uc.Chrome(options=options)

            # Настройка таймаутов и размера окна
            driver.set_page_load_timeout(self.config.page_load_timeout)
            driver.set_script_timeout(self.config.page_load_timeout)
            driver.implicitly_wait(0)  # Только явные WebDriverWait

            driver.set_window_size(*self.config.window_size)

            # Скрытие WebDriver
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            logger.debug("Chrome драйвер создан")
            return driver

        except ImportError:
            logger.warning("undetected_chromedriver не установлен")
            raise

    async def _close_driver(self, driver: Any) -> None:
        """Закрытие драйвера."""
        try:
            if hasattr(driver, "quit"):
                driver.quit()
                logger.debug("Драйвер закрыт")
        except Exception as e:
            logger.error(f"Ошибка при закрытии драйвера: {e}")


# Заглушка для будущей расширенной реализации
class AdvancedDriverManager(SimpleDriverManager):
    """
    Расширенный менеджер драйверов с поддержкой:
    - Пул драйверов с фиксированным размером
    - Health-check драйверов
    - Балансировка нагрузки
    - Поддержка прокси и ротации user-agent

    Пока является заглушкой для будущего расширения.
    """

    def __init__(self, config: Optional[DriverConfig] = None, pool_size: int = 5):
        """
        Инициализация расширенного менеджера драйверов.

        Args:
            config: Конфигурация драйверов
            pool_size: Размер пула драйверов
        """
        super().__init__(config)
        self.pool_size = pool_size
        self._health_check_interval = 60  # секунды

        logger.info(f"AdvancedDriverManager инициализирован с pool_size={pool_size}")

    async def _health_check(self) -> None:
        """Проверка здоровья драйверов в пуле."""
        # Заглушка для будущей реализации
        pass

    async def _rotate_user_agent(self, driver: Any) -> None:
        """Ротация user-agent для драйвера."""
        # Заглушка для будущей реализации
        pass


# Фабрика для создания менеджеров драйверов
def create_driver_manager(
    manager_type: str = "simple", config: Optional[DriverConfig] = None, **kwargs
) -> DriverManagerInterface:
    """
    Создание менеджера драйверов указанного типа.

    Args:
        manager_type: Тип менеджера ("simple" или "advanced")
        config: Конфигурация драйверов
        **kwargs: Дополнительные параметры для конкретного менеджера

    Returns:
        Экземпляр DriverManagerInterface

    Raises:
        ValueError: Если указан неизвестный тип менеджера
    """
    if manager_type == "simple":
        return SimpleDriverManager(config)
    elif manager_type == "advanced":
        return AdvancedDriverManager(config, **kwargs)
    else:
        raise ValueError(f"Неизвестный тип менеджера: {manager_type}")
