import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as c:
        r = await c.post(
            'https://places.googleapis.com/v1/places:searchText',
            headers={
                'X-Goog-Api-Key': 'AIzaSyDcjgRCCrnpRRvt4M4oBuSPxjxcNGTZEPQ',
                'X-Goog-FieldMask': 'places.id',
                'Content-Type': 'application/json'
            },
            json={'textQuery': 'cafes in toronto'}
        )
        print(r.status_code)
        print(r.text)

if __name__ == "__main__":
    asyncio.run(test())
