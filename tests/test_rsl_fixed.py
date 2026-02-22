import pytest
from api_clients import get_from_rsl, get_from_rsl_async
import aiohttp


@pytest.mark.network
def test_get_from_rsl_sync_returns_data_for_known_isbn():
    """Проверка синхронного клиента РГБ на известном ISBN."""
    result = get_from_rsl("9785977520966")
    if result is None:
        pytest.skip("RSL sync: не удалось получить данные (None)")
    assert "title" in result and result["title"]


@pytest.mark.network
@pytest.mark.asyncio
async def test_get_from_rsl_async_returns_data_for_known_isbn():
    """Проверка асинхронного клиента РГБ на известном ISBN."""
    async with aiohttp.ClientSession() as session:
        result = await get_from_rsl_async(session, "9785977520966")
    if result is None:
        pytest.skip("RSL async: не удалось получить данные (None)")
    assert "title" in result and result["title"]
