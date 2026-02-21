import isbnlib
from typing import Optional


def replace_similar_digits(text: str) -> str:
    """
    Заменяет символы, похожие на цифры, на соответствующие цифры.
    Например, кириллическая 'О' (U+041E) и латинская 'O' (U+004F) заменяются на '0'.
    Также заменяет строчную кириллическую 'о' (U+043E) на '0'.
    """
    # Таблица замен: ключ - символ для замены, значение - цифра
    mapping = {
        # Ноль
        'О': '0',  # кириллическая заглавная
        'O': '0',  # латинская заглавная
        'о': '0',  # кириллическая строчная
        'o': '0',  # латинская строчная (редко, но возможно)
    }
    for char, digit in mapping.items():
        text = text.replace(char, digit)
    return text


def normalize_isbn(isbn: str) -> Optional[str]:
    """
    Принимает ISBN (10 или 13 знаков, с дефисами или без),
    возвращает канонический 13-значный код (без дефисов) или None, если код невалиден.
    """
    # Заменяем похожие на цифры символы (О/O -> 0 и т.д.)
    isbn = replace_similar_digits(isbn)
    clean = isbnlib.canonical(isbn)
    if not clean:
        return None
    if isbnlib.is_isbn13(clean):
        return clean
    if isbnlib.is_isbn10(clean):
        return isbnlib.to_isbn13(clean)
    return None
