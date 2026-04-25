import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as c:
        # Using the EXACT key from the user's last message
        key = "AIzaSyDQXy9LDWQ9sCoRWlbfJIIAvIYEdRpLSSQ"
        cx = "833fdcbdf8d8841e7"
        url = f'https://www.googleapis.com/customsearch/v1?q=test&key={key}&cx={cx}'
        r = await c.get(url)
        print(r.status_code)
        print(r.text)

if __name__ == "__main__":
    asyncio.run(test())
