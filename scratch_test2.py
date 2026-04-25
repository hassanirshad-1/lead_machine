import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as c:
        r = await c.get('http://127.0.0.1:8000/leads')
        print(r.status_code)
        if r.status_code != 200:
            print(r.text[-2000:])
        else:
            print("Success!")

if __name__ == "__main__":
    asyncio.run(test())
