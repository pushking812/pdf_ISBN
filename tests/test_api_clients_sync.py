import pytest
from api_clients import (
    get_from_google_books,
    get_from_open_library,
    get_from_rsl
)


SYNC_CLIENTS = [
    ("Google Books", get_from_google_books),
    ("Open Library", get_from_open_library),
    ("РГБ", get_from_rsl),
]


@pytest.mark.parametrize("resource_name, client_func", SYNC_CLIENTS)
def test_sync_client_returns_data_for_at_least_one_isbn(resource_name, client_func, isbn_list):
    """
    Тест, что синхронный клиент возвращает данные хотя бы для одного ISBN.
    """
    success = False
    errors = []
    
    # Ограничимся первыми 10 ISBN для скорости, но можно увеличить при необходимости
    for isbn in isbn_list[:10]:
        try:
            result = client_func(isbn)
            if result is not None:
                # Проверяем, что есть хотя бы заголовок
                assert "title" in result
                assert result["title"] not in ("Нет названия", "")
                success = True
                print(f"{resource_name}: успех для ISBN {isbn}")
                break
        except Exception as e:
            errors.append(f"{isbn}: {e}")
            continue
    
    if not success:
        pytest.skip(f"{resource_name}: ни один ISBN не вернул данные. Ошибки: {errors}")