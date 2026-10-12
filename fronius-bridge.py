from typing import Any
import aiohttp
import asyncio
import json


async def retrieve_solar_output(url: str) -> int:
    timeout = aiohttp.ClientTimeout(total=5)  # 5 seconds
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                status = response.status
                content = await response.text()

                if status == 200:
                    result: dict[str, Any] = json.loads(content)
                    power_output: int = result["Body"]["Data"]["Inverters"]["1"]["P"]
                    return power_output
                else:
                    return 0
    except asyncio.TimeoutError as e:
        print(f"Timeout occurred while fetching the URL. {e}")
        return 0
    except aiohttp.ClientError as e:
        print(f"An error occurred: {e}")
        return 0
