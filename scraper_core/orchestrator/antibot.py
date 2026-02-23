"""
Обработчик анти-бот защиты.

Предоставляет стратегии для обхода блокировок и обнаружения CAPTCHA.
"""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class BlockType(Enum):
    """Типы блокировок."""

    CAPTCHA = "captcha"
    RATE_LIMIT = "rate_limit"
    IP_BLOCK = "ip_block"
    USER_AGENT_BLOCK = "user_agent_block"
    JAVASCRIPT_CHALLENGE = "javascript_challenge"
    UNKNOWN = "unknown"


@dataclass
class BlockDetection:
    """Обнаружение блокировки."""

    block_type: BlockType
    confidence: float  # 0.0 - 1.0
    evidence: List[str]
    suggested_action: str


@dataclass
class AntiBotConfig:
    """Конфигурация анти-бот обработчика."""

    enable_proxy_rotation: bool = False
    enable_user_agent_rotation: bool = True
    enable_request_delays: bool = True
    min_delay_seconds: float = 1.0
    max_delay_seconds: float = 3.0
    max_retries_on_block: int = 3
    captcha_solver_enabled: bool = False
    proxy_list: Optional[List[str]] = None
    user_agent_list: Optional[List[str]] = None


class AntiBotHandlerInterface(ABC):
    """Интерфейс обработчика анти-бот защиты."""

    @abstractmethod
    async def detect_block(
        self, response: Any, html: Optional[str] = None
    ) -> Optional[BlockDetection]:
        """
        Обнаружение блокировки в ответе.

        Args:
            response: Ответ (может быть requests.Response, selenium WebDriver и т.д.)
            html: HTML содержимое (опционально)

        Returns:
            BlockDetection или None если блокировка не обнаружена
        """
        pass

    @abstractmethod
    async def apply_evasion_strategy(self, block_type: BlockType) -> Dict[str, Any]:
        """
        Применение стратегии обхода блокировки.

        Args:
            block_type: Тип блокировки

        Returns:
            Словарь с примененными изменениями (новый user-agent, прокси и т.д.)
        """
        pass

    @abstractmethod
    async def prepare_request(self) -> Dict[str, Any]:
        """
        Подготовка запроса с применением анти-бот мер.

        Returns:
            Словарь с параметрами для запроса
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики работы анти-бот обработчика.

        Returns:
            Словарь со статистикой
        """
        pass


class SimpleAntiBotHandler(AntiBotHandlerInterface):
    """
    Простой обработчик анти-бот защиты с базовыми стратегиями.

    Предоставляет:
    - Ротацию user-agent
    - Случайные задержки между запросами
    - Базовое обнаружение CAPTCHA и rate limit
    """

    # Список распространенных user-agent
    DEFAULT_USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    ]

    # Ключевые слова для обнаружения блокировок
    CAPTCHA_KEYWORDS = [
        "captcha",
        "recaptcha",
        "hcaptcha",
        "verify you are human",
        "подтвердите что вы человек",
    ]
    RATE_LIMIT_KEYWORDS = [
        "rate limit",
        "too many requests",
        "429",
        "запросов слишком много",
        "подождите",
    ]
    BLOCK_KEYWORDS = ["blocked", "access denied", "доступ запрещен", "forbidden", "403"]

    def __init__(self, config: Optional[AntiBotConfig] = None):
        """
        Инициализация обработчика анти-бот защиты.

        Args:
            config: Конфигурация обработчика
        """
        self.config = config or AntiBotConfig()
        self._current_user_agent: Optional[str] = None
        self._current_proxy: Optional[str] = None
        self._stats = {
            "blocks_detected": 0,
            "evasion_attempts": 0,
            "successful_evasions": 0,
            "captcha_detections": 0,
            "rate_limit_detections": 0,
        }

        # Инициализация списков
        self.user_agents = self.config.user_agent_list or self.DEFAULT_USER_AGENTS
        self.proxies = self.config.proxy_list or []

        # Выбор начального user-agent
        if self.config.enable_user_agent_rotation and self.user_agents:
            self._current_user_agent = random.choice(self.user_agents)

        logger.info(
            f"SimpleAntiBotHandler инициализирован с {len(self.user_agents)} user-agent"
        )

    async def detect_block(
        self, response: Any, html: Optional[str] = None
    ) -> Optional[BlockDetection]:
        """
        Обнаружение блокировки в ответе.

        Args:
            response: Ответ (может быть requests.Response, selenium WebDriver и т.д.)
            html: HTML содержимое (опционально)

        Returns:
            BlockDetection или None если блокировка не обнаружена
        """
        detection_data = []
        html_text = html or ""

        # Если response - объект requests.Response
        if hasattr(response, "status_code"):
            status_code = response.status_code

            # Проверка кодов состояния HTTP
            if status_code == 429:
                detection_data.append("HTTP 429 Too Many Requests")
                return BlockDetection(
                    block_type=BlockType.RATE_LIMIT,
                    confidence=0.9,
                    evidence=detection_data,
                    suggested_action="Увеличить задержки, сменить IP/user-agent",
                )
            elif status_code == 403:
                detection_data.append("HTTP 403 Forbidden")
                return BlockDetection(
                    block_type=BlockType.IP_BLOCK,
                    confidence=0.8,
                    evidence=detection_data,
                    suggested_action="Сменить IP/user-agent, использовать прокси",
                )
            elif status_code == 503:
                detection_data.append("HTTP 503 Service Unavailable")
                return BlockDetection(
                    block_type=BlockType.RATE_LIMIT,
                    confidence=0.7,
                    evidence=detection_data,
                    suggested_action="Увеличить задержки, повторить позже",
                )

        # Анализ текста/HTML на наличие ключевых слов блокировок
        text_to_analyze = html_text.lower()

        # Проверка CAPTCHA
        captcha_evidence = []
        for keyword in self.CAPTCHA_KEYWORDS:
            if keyword in text_to_analyze:
                captcha_evidence.append(f"Найдено ключевое слово: {keyword}")

        if captcha_evidence:
            self._stats["captcha_detections"] += 1
            return BlockDetection(
                block_type=BlockType.CAPTCHA,
                confidence=0.85,
                evidence=captcha_evidence,
                suggested_action="Использовать сервис решения CAPTCHA или сделать паузу",
            )

        # Проверка rate limit
        rate_limit_evidence = []
        for keyword in self.RATE_LIMIT_KEYWORDS:
            if keyword in text_to_analyze:
                rate_limit_evidence.append(f"Найдено ключевое слово: {keyword}")

        if rate_limit_evidence:
            self._stats["rate_limit_detections"] += 1
            return BlockDetection(
                block_type=BlockType.RATE_LIMIT,
                confidence=0.75,
                evidence=rate_limit_evidence,
                suggested_action="Увеличить задержки между запросами",
            )

        # Проверка общих блокировок
        block_evidence = []
        for keyword in self.BLOCK_KEYWORDS:
            if keyword in text_to_analyze:
                block_evidence.append(f"Найдено ключевое слово: {keyword}")

        if block_evidence:
            return BlockDetection(
                block_type=BlockType.UNKNOWN,
                confidence=0.6,
                evidence=block_evidence,
                suggested_action="Сменить IP/user-agent, увеличить задержки",
            )

        # Если ничего не найдено
        return None

    async def apply_evasion_strategy(self, block_type: BlockType) -> Dict[str, Any]:
        """
        Применение стратегии обхода блокировки.

        Args:
            block_type: Тип блокировки

        Returns:
            Словарь с примененными изменениями
        """
        self._stats["evasion_attempts"] += 1
        applied_changes = {}

        if block_type == BlockType.RATE_LIMIT:
            # Для rate limit увеличиваем задержки
            if self.config.enable_request_delays:
                new_min_delay = self.config.min_delay_seconds * 2
                new_max_delay = self.config.max_delay_seconds * 2
                applied_changes["increased_delays"] = {
                    "min": new_min_delay,
                    "max": new_max_delay,
                }
                logger.info(
                    f"Увеличены задержки для обхода rate limit: {new_min_delay}-{new_max_delay} сек"
                )

            # Ротация user-agent
            if self.config.enable_user_agent_rotation and self.user_agents:
                new_ua = self._rotate_user_agent()
                applied_changes["new_user_agent"] = new_ua

            self._stats["successful_evasions"] += 1

        elif block_type == BlockType.CAPTCHA:
            # Для CAPTCHA используем разные стратегии
            applied_changes["action"] = "captcha_detected"

            if self.config.captcha_solver_enabled:
                applied_changes["use_captcha_solver"] = True
                logger.info("Использование сервиса решения CAPTCHA")
            else:
                # Без сервиса решения CAPTCHA - делаем длинную паузу
                applied_changes["long_pause"] = 30  # секунд
                logger.info("CAPTCHA обнаружена, делаем паузу 30 секунд")

            # Ротация user-agent и прокси
            if self.config.enable_user_agent_rotation and self.user_agents:
                new_ua = self._rotate_user_agent()
                applied_changes["new_user_agent"] = new_ua

            if self.config.enable_proxy_rotation and self.proxies:
                new_proxy = self._rotate_proxy()
                applied_changes["new_proxy"] = new_proxy

            self._stats["successful_evasions"] += 1

        elif block_type in [BlockType.IP_BLOCK, BlockType.USER_AGENT_BLOCK]:
            # Для блокировок по IP/user-agent меняем оба параметра
            if self.config.enable_user_agent_rotation and self.user_agents:
                new_ua = self._rotate_user_agent()
                applied_changes["new_user_agent"] = new_ua

            if self.config.enable_proxy_rotation and self.proxies:
                new_proxy = self._rotate_proxy()
                applied_changes["new_proxy"] = new_proxy

            self._stats["successful_evasions"] += 1

        else:
            # Для неизвестных блокировок применяем комбинированную стратегию
            applied_changes["combined_strategy"] = True

            if self.config.enable_user_agent_rotation and self.user_agents:
                new_ua = self._rotate_user_agent()
                applied_changes["new_user_agent"] = new_ua

            if self.config.enable_request_delays:
                applied_changes["random_delay_applied"] = True

            self._stats["successful_evasions"] += 1

        self._stats["blocks_detected"] += 1
        return applied_changes

    async def prepare_request(self) -> Dict[str, Any]:
        """
        Подготовка запроса с применением анти-бот мер.

        Returns:
            Словарь с параметрами для запроса
        """
        request_params = {}

        # Добавление user-agent
        if self.config.enable_user_agent_rotation and self._current_user_agent:
            request_params["headers"] = {"User-Agent": self._current_user_agent}

        # Добавление прокси
        if self.config.enable_proxy_rotation and self._current_proxy:
            request_params["proxy"] = self._current_proxy

        # Применение случайной задержки
        if self.config.enable_request_delays:
            delay = random.uniform(
                self.config.min_delay_seconds, self.config.max_delay_seconds
            )
            await asyncio.sleep(delay)
            request_params["applied_delay"] = delay

        return request_params

    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики работы анти-бот обработчика.

        Returns:
            Словарь со статистикой
        """
        return {
            **self._stats,
            "config": {
                "enable_proxy_rotation": self.config.enable_proxy_rotation,
                "enable_user_agent_rotation": self.config.enable_user_agent_rotation,
                "enable_request_delays": self.config.enable_request_delays,
                "user_agents_count": len(self.user_agents),
                "proxies_count": len(self.proxies),
            },
        }

    def _rotate_user_agent(self) -> str:
        """Ротация user-agent."""
        if not self.user_agents:
            return self._current_user_agent or ""

        # Выбираем случайный user-agent, отличный от текущего
        available_agents = [
            ua for ua in self.user_agents if ua != self._current_user_agent
        ]
        if not available_agents:
            available_agents = self.user_agents

        new_agent = random.choice(available_agents)
        self._current_user_agent = new_agent

        logger.debug(f"User-agent изменен: {new_agent[:50]}...")
        return new_agent

    def _rotate_proxy(self) -> Optional[str]:
        """Ротация прокси."""
        if not self.proxies:
            return None

        # Выбираем случайный прокси
        new_proxy = random.choice(self.proxies)
        self._current_proxy = new_proxy

        logger.debug(f"Прокси изменен: {new_proxy}")
        return new_proxy


# Заглушка для будущей расширенной реализации
class AdvancedAntiBotHandler(SimpleAntiBotHandler):
    """
    Расширенный обработчик анти-бот защиты.

    Предоставляет дополнительные возможности:
    - Машинное обучение для обнаружения блокировок
    - Интеграция с сервисами решения CAPTCHA
    - Адаптивные стратегии обхода
    - Анализ поведения браузера

    Пока является заглушкой для будущего расширения.
    """

    def __init__(self, config: Optional[AntiBotConfig] = None):
        """
        Инициализация расширенного обработчика анти-бот защиты.

        Args:
            config: Конфигурация обработчика
        """
        super().__init__(config)

        # Дополнительные возможности для будущей реализации
        self._behavior_patterns: Dict[str, Any] = {}
        self._ml_model_loaded = False

        logger.info(
            "AdvancedAntiBotHandler инициализирован (заглушка для будущего расширения)"
        )

    async def detect_block(
        self, response: Any, html: Optional[str] = None
    ) -> Optional[BlockDetection]:
        """
        Расширенное обнаружение блокировок с использованием ML.

        Args:
            response: Ответ
            html: HTML содержимое

        Returns:
            BlockDetection или None
        """
        # Сначала используем базовую логику
        basic_detection = await super().detect_block(response, html)

        if basic_detection:
            return basic_detection

        # Дополнительная логика для будущей реализации
        # Здесь можно добавить анализ с помощью ML моделей
        # или более сложную эвристику

        return None

    async def analyze_behavior_patterns(
        self, resource_id: str, behavior_data: Dict[str, Any]
    ) -> None:
        """
        Анализ паттернов поведения для конкретного ресурса.

        Args:
            resource_id: Идентификатор ресурса
            behavior_data: Данные о поведении
        """
        # Заглушка для будущей реализации
        # Здесь можно сохранять паттерны поведения для каждого ресурса
        # и использовать их для адаптивных стратегий обхода
        self._behavior_patterns[resource_id] = behavior_data
        logger.debug(f"Паттерны поведения сохранены для ресурса {resource_id}")


# Фабрика для создания обработчиков анти-бот защиты
def create_antibot_handler(
    handler_type: str = "simple", config: Optional[AntiBotConfig] = None, **kwargs
) -> AntiBotHandlerInterface:
    """
    Создание обработчика анти-бот защиты указанного типа.

    Args:
        handler_type: Тип обработчика ("simple" или "advanced")
        config: Конфигурация обработчика
        **kwargs: Дополнительные параметры

    Returns:
        Экземпляр AntiBotHandlerInterface

    Raises:
        ValueError: Если указан неизвестный тип обработчика
    """
    if handler_type == "simple":
        return SimpleAntiBotHandler(config)
    elif handler_type == "advanced":
        return AdvancedAntiBotHandler(config, **kwargs)
    else:
        raise ValueError(f"Неизвестный тип обработчика: {handler_type}")
