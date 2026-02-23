"""
Утилиты для работы с ISBN: валидация, нормализация, извлечение.

Функции адаптированы из pdf_extract_isbn.py с улучшениями для использования
во всей системе скрапинга.
"""

import re
from typing import Optional, List, Tuple


def validate_isbn10(isbn: str) -> bool:
    """
    Проверка контрольной суммы для ISBN-10.

    Args:
        isbn: ISBN-10 строка (10 символов)

    Returns:
        True если ISBN-10 валиден, иначе False

    Пример:
        >>> validate_isbn10("0306406152")
        True
        >>> validate_isbn10("0306406153")
        False
    """
    if len(isbn) != 10:
        return False

    total = 0
    for i in range(9):
        if not isbn[i].isdigit():
            return False
        total += int(isbn[i]) * (10 - i)

    last = isbn[9]
    if last == "X":
        total += 10
    elif last.isdigit():
        total += int(last)
    else:
        return False

    return total % 11 == 0


def validate_isbn13(isbn: str) -> bool:
    """
    Проверка контрольной суммы для ISBN-13.

    Args:
        isbn: ISBN-13 строка (13 цифр)

    Returns:
        True если ISBN-13 валиден, иначе False

    Пример:
        >>> validate_isbn13("9780306406157")
        True
        >>> validate_isbn13("9780306406158")
        False
    """
    if len(isbn) != 13 or not isbn.isdigit():
        return False

    total = 0
    for i in range(12):
        digit = int(isbn[i])
        total += digit * (1 if i % 2 == 0 else 3)

    check = (10 - (total % 10)) % 10
    return int(isbn[12]) == check


def validate_isbn(isbn: str) -> bool:
    """
    Проверка валидности ISBN (автоматически определяет тип).

    Args:
        isbn: ISBN строка (может содержать дефисы)

    Returns:
        True если ISBN валиден (ISBN-10 или ISBN-13), иначе False
    """
    clean = normalize_isbn(isbn)
    if len(clean) == 10:
        return validate_isbn10(clean)
    elif len(clean) == 13:
        return validate_isbn13(clean)
    return False


def normalize_isbn(isbn: str) -> str:
    """
    Нормализация ISBN: удаление дефисов, пробелов, приведение к верхнему регистру.

    Args:
        isbn: ISBN строка (может содержать дефисы, пробелы)

    Returns:
        Очищенная ISBN строка

    Пример:
        >>> normalize_isbn("978-0-306-40615-7")
        "9780306406157"
        >>> normalize_isbn("0-306-40615-2")
        "0306406152"
    """
    if not isbn:
        return ""

    # Удаляем все не-цифры и не-X символы, кроме последнего X
    clean = re.sub(r"[^\dX]", "", isbn.upper())

    # Если есть X, но не на последней позиции - это ошибка
    if "X" in clean and clean[-1] != "X":
        # Удаляем X не на последней позиции
        clean = clean.replace("X", "")

    return clean


def extract_isbn_from_text(text: str, strict: bool = True) -> Optional[str]:
    """
    Извлекает ISBN из текста (адаптация find_isbn_in_text из pdf_extract_isbn.py).

    Args:
        text: Текст для поиска ISBN
        strict: True - требует префикс 'ISBN', False - ищет любые последовательности

    Returns:
        Найденный ISBN или None
    """
    # Импортируем replace_similar_digits из utils если доступен
    try:
        from utils import replace_similar_digits

        text = replace_similar_digits(text)
    except ImportError:
        # Простая замена похожих символов если utils не доступен
        replacements = {
            "О": "0",
            "о": "0",
            "O": "0",
            "o": "0",  # Кириллическая и латинская O
            "l": "1",
            "I": "1",
            "|": "1",  # Похожие на 1
            "З": "3",
            "з": "3",  # Похожие на 3
            "Ч": "4",
            "ч": "4",  # Похожие на 4
            "б": "6",  # Похожие на 6
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

    # Сначала ISBN-13 (978/979), иначе первые 10 цифр ISBN-13 ошибочно матчатся как ISBN-10
    if strict:
        patterns = [
            r"(?:ISBN(?:-13)?:?\s*)?((?:97[89])[-\s]?(?:\d[-\s]?){9}\d)",  # ISBN-13
            r"(?:ISBN(?:-10)?:?\s*)?((?:\d[-\s]?){9}[\dX])",  # ISBN-10
        ]
    else:
        patterns = [
            r"((?:97[89])[-\s]?(?:\d[-\s]?){9}\d)",  # ISBN-13 без префикса
            r"((?:\d[-\s]?){9}[\dX])",  # ISBN-10 без префикса
        ]

    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            candidate = match.group(1)
            clean = normalize_isbn(candidate)

            if len(clean) == 13 and validate_isbn13(clean):
                return clean
            if len(clean) == 10 and validate_isbn10(clean):
                return clean

    return None


def isbn_to_isbn13(isbn10: str) -> Optional[str]:
    """
    Конвертация ISBN-10 в ISBN-13.

    Args:
        isbn10: Валидный ISBN-10

    Returns:
        ISBN-13 или None если конвертация невозможна
    """
    if not validate_isbn10(isbn10):
        return None

    # Префикс для книг: 978, для некоторых 979
    prefix = "978"

    # Берем первые 9 цифр ISBN-10
    isbn12 = prefix + isbn10[:-1]

    # Вычисляем контрольную сумму для ISBN-13
    total = 0
    for i in range(12):
        digit = int(isbn12[i])
        total += digit * (1 if i % 2 == 0 else 3)

    check_digit = (10 - (total % 10)) % 10
    return isbn12 + str(check_digit)


def isbn_to_isbn10(isbn13: str) -> Optional[str]:
    """
    Конвертация ISBN-13 в ISBN-10 (только для префикса 978).

    Args:
        isbn13: Валидный ISBN-13 с префиксом 978

    Returns:
        ISBN-10 или None если конвертация невозможна
    """
    if not validate_isbn13(isbn13) or not isbn13.startswith("978"):
        return None

    # Убираем префикс 978
    isbn9 = isbn13[3:-1]  # Убираем префикс и последнюю цифру

    # Вычисляем контрольную сумму для ISBN-10
    total = 0
    for i in range(9):
        total += int(isbn9[i]) * (10 - i)

    check_digit = 11 - (total % 11)
    if check_digit == 10:
        check_char = "X"
    elif check_digit == 11:
        check_char = "0"
    else:
        check_char = str(check_digit)

    return isbn9 + check_char


def format_isbn(isbn: str, with_dashes: bool = True) -> str:
    """
    Форматирование ISBN с дефисами в стандартном формате.

    Args:
        isbn: ISBN строка (очищенная)
        with_dashes: True - с дефисами, False - без

    Returns:
        Отформатированный ISBN
    """
    clean = normalize_isbn(isbn)

    if not with_dashes:
        return clean

    if len(clean) == 10:
        # ISBN-10: группа-издатель-номер-контрольная
        return f"{clean[0]}-{clean[1:4]}-{clean[4:9]}-{clean[9]}"
    elif len(clean) == 13:
        # ISBN-13: префикс-группа-издатель-номер-контрольная
        return f"{clean[0:3]}-{clean[3]}-{clean[4:6]}-{clean[6:12]}-{clean[12]}"

    return clean


def extract_multiple_isbns(text: str, strict: bool = True) -> List[str]:
    """
    Извлекает все ISBN из текста.

    Args:
        text: Текст для поиска
        strict: Режим поиска

    Returns:
        Список найденных уникальных ISBN
    """
    isbns = set()

    # Используем регулярные выражения для поиска всех возможных ISBN
    if strict:
        patterns = [
            r"(?:ISBN(?:-13)?:?\s*)?((?:97[89])[-\s]?(?:\d[-\s]?){9}\d)",
            r"(?:ISBN(?:-10)?:?\s*)?((?:\d[-\s]?){9}[\dX])",
        ]
    else:
        patterns = [
            r"((?:97[89])[-\s]?(?:\d[-\s]?){9}\d)",
            r"((?:\d[-\s]?){9}[\dX])",
        ]

    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            candidate = match.group(1)
            clean = normalize_isbn(candidate)

            if len(clean) == 13 and validate_isbn13(clean):
                isbns.add(clean)
            elif len(clean) == 10 and validate_isbn10(clean):
                isbns.add(clean)

    return list(isbns)


def validate_and_normalize_isbns(isbns: List[str]) -> Tuple[List[str], List[str]]:
    """
    Валидация и нормализация списка ISBN.

    Args:
        isbns: Список ISBN строк

    Returns:
        Кортеж (валидные_ISBN, невалидные_ISBN)
    """
    valid = []
    invalid = []

    for isbn in isbns:
        normalized = normalize_isbn(isbn)
        if validate_isbn(normalized):
            valid.append(normalized)
        else:
            invalid.append(isbn)

    return valid, invalid


if __name__ == "__main__":
    # Тесты
    test_isbn10 = "0306406152"
    test_isbn13 = "9780306406157"

    print(f"validate_isbn10('{test_isbn10}'): {validate_isbn10(test_isbn10)}")
    print(f"validate_isbn13('{test_isbn13}'): {validate_isbn13(test_isbn13)}")
    print(f"normalize_isbn('978-0-306-40615-7'): {normalize_isbn('978-0-306-40615-7')}")
    print(f"isbn_to_isbn13('{test_isbn10}'): {isbn_to_isbn13(test_isbn10)}")
    print(f"isbn_to_isbn10('{test_isbn13}'): {isbn_to_isbn10(test_isbn13)}")
