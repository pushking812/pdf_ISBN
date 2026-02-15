import isbnlib
from typing import Optional

def normalize_isbn(isbn: str) -> Optional[str]:
    """
    Принимает ISBN (10 или 13 знаков, с дефисами или без),
    возвращает канонический 13-значный код (без дефисов) или None, если код невалиден.
    """
    clean = isbnlib.canonical(isbn)
    if not clean:
        return None
    if isbnlib.is_isbn13(clean):
        return clean
    if isbnlib.is_isbn10(clean):
        return isbnlib.to_isbn13(clean)
    return None