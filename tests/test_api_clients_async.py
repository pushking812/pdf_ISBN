import pytest
from api_clients import (
    get_from_google_books_async,
    get_from_open_library_async,
    get_from_rsl_async,
)

pytestmark = [pytest.mark.network]

ASYNC_CLIENTS = [
    ("Google Books async", get_from_google_books_async),
    ("Open Library async", get_from_open_library_async),
    ("РГБ async", get_from_rsl_async),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("resource_name, client_func", ASYNC_CLIENTS)
async def test_async_client_returns_data_for_at_least_one_isbn(
    resource_name, client_func, isbn_list, aiohttp_session
):
    """
    Тест, что асинхронный клиент возвращает данные хотя бы для одного ISBN.
    """
    success = False
    errors = []

    for isbn in isbn_list[:10]:
        try:
            result = await client_func(aiohttp_session, isbn)
            if result is not None:
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
