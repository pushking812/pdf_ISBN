import sys
sys.path.insert(0, '.')
from api_clients import get_from_rsl

result = get_from_rsl('9785977520966')
print("Результат запроса к RSL:")
if result:
    print(f"Название: {result['title']}")
    print(f"Авторы: {result['authors']}")
    print(f"Год: {result['year']}")
    print(f"Страницы: {result['pages']}")
    print(f"Источник: {result['source']}")
else:
    print("Не удалось получить данные (None)")

# Также проверим асинхронную версию
import asyncio
import aiohttp
from api_clients import get_from_rsl_async

async def test_async():
    async with aiohttp.ClientSession() as session:
        result = await get_from_rsl_async(session, '9785977520966')
        print("\nАсинхронный результат:")
        if result:
            print(f"Название: {result['title']}")
            print(f"Авторы: {result['authors']}")
            print(f"Год: {result['year']}")
            print(f"Страницы: {result['pages']}")
            print(f"Источник: {result['source']}")
        else:
            print("Не удалось получить данные (None)")

asyncio.run(test_async())