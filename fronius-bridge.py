from typing import Any
import aiohttp
import asyncio
import json
import os
import signal
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()  # reads .env from the working directory (see .env.example)


# -- Config -- from .env / environment (see .env.example) -----------------------
FRONIUS_URL    = os.environ.get("FRONIUS_URL", "http://192.168.68.107/solar_api/v1/GetPowerFlowRealtimeData.fcgi")
INGEST_URL     = os.environ.get("INGEST_URL", "http://192.168.68.141:8000/api/v1/solar/readings")
INGEST_API_KEY = os.environ.get("INGEST_API_KEY", "")
POLL_SECONDS   = int(os.environ.get("POLL_SECONDS", "60"))


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


# -- Ingest POST (home-energy-server) --------------------------------------------
_outbox: list[dict] = []


def solar_payload(watts: float) -> dict:
    return {
        "time": datetime.now(timezone.utc).isoformat(),
        "average_watts": round(float(watts), 3),
    }


async def post_reading(session: aiohttp.ClientSession, payload: dict) -> bool:
    headers = {"Content-Type": "application/json", "X-API-Key": INGEST_API_KEY}
    try:
        async with session.post(INGEST_URL, json=payload, headers=headers) as resp:
            ok = 200 <= resp.status < 300
            if not ok:
                body = await resp.text()
                print(f"  [INGEST] HTTP {resp.status}: {body[:120]}")
            return ok
    except aiohttp.ClientError as e:
        print(f"  [INGEST] server unreachable: {e}")
        return False


async def send_reading(session: aiohttp.ClientSession, payload: dict) -> None:
    if not INGEST_API_KEY:
        return  # console-only mode
    if await post_reading(session, payload):
        await flush_outbox(session)
        return
    _outbox.append(payload)
    if len(_outbox) > 720:  # ~12 h of minute data, then drop the oldest
        _outbox.pop(0)
        print("  [INGEST] outbox overflow, dropped oldest reading")
    print(f"  [INGEST] queued for retry ({len(_outbox)} in outbox)")


async def flush_outbox(session: aiohttp.ClientSession) -> None:
    flushed = False
    while _outbox:
        if not await post_reading(session, _outbox[0]):
            break
        _outbox.pop(0)
        flushed = True
    if flushed:
        print("  [INGEST] outbox flushed")


# -- Main loop --------------------------------------------------------------------
async def main_loop() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass  # Windows

    async with aiohttp.ClientSession() as session:
        while not stop.is_set():
            try:
                watts = await retrieve_solar_output(FRONIUS_URL)
            except Exception as e:
                # e.g. empty Inverters dict from the inverter (no data yet)
                print(f"  [POLL] error reading inverter: {e}")
                watts = 0

            payload = solar_payload(watts)
            print(f"  [POLL] {payload['time']}  {watts} W")
            await send_reading(session, payload)

            try:
                await asyncio.wait_for(stop.wait(), timeout=POLL_SECONDS)
            except asyncio.TimeoutError:
                pass
    print("fronius-bridge stopped")


if __name__ == "__main__":
    ingest_state = INGEST_URL if INGEST_API_KEY else "disabled (no INGEST_API_KEY)"
    print(f"fronius-bridge: host={FRONIUS_HOST} poll={POLL_SECONDS}s ingest={ingest_state}")
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
