# fronius-bridge

The solar-side bridge for [home-energy-server](https://github.com/benedict-chng/home-energy-server).
Reads the live energy output from a Fronius inverter on the home LAN and
posts each reading to the server's solar ingest API.

Sibling projects:

- [home-energy-server](https://github.com/benedict-chng/home-energy-server) —
  FastAPI + TimescaleDB server that stores grid (Powerpal) and solar (Fronius) readings
- [powerpal-bridge](https://github.com/benedict-chng/powerpal-bridge) —
  the grid-side BLE bridge for the Powerpal meter

## What it does

1. Polls the Fronius inverter on the home LAN for its current AC output (watts)
2. POSTs one reading per interval to the solar ingest endpoint:

```json
{"time": "2026-10-12T11:00:00+00:00", "average_watts": 1850.0}
```

`POST {INGEST_URL}` with header `X-API-Key: <INGEST_API_KEY>` — the server's
solar schema takes exactly two fields, both mandatory:

| Field | Type | Rules |
|-------|------|-------|
| `time` | ISO 8601 **with UTC offset** | stored as UTC; duplicate timestamps are skipped (idempotent) |
| `average_watts` | float ≥ 0 | average inverter output over the interval |

Extra fields are rejected — keep payloads to exactly these two keys.

## Status

`fronius-bridge.py` implements the full loop: polls the Fronius Solar API
for current output (watts), and POSTs one reading per `POLL_SECONDS` to
home-energy-server's solar ingest endpoint using aiohttp. Failed posts
queue in memory (~12 h) and retry; the server deduplicates by time.

## Configuration (.env)

```bash
cp .env.example .env
# edit with your values
```

`python-dotenv` (the one entry in `requirements.txt`) loads `.env` at
startup; real environment variables still take precedence.

| Variable | Example | Purpose |
|----------|---------|---------|
| `FRONIUS_URL` | `http://192.168.68.107/solar_api/v1/GetPowerFlowRealtimeData.fcgi` | Fronius inverter URL on the home LAN |
| `INGEST_URL` | `http://192.168.68.141:8000/api/v1/solar/readings` | Solar ingest endpoint |
| `INGEST_API_KEY` | *(paste the real key)* | The server's ingest API key (same key as powerpal-bridge) |
| `POLL_SECONDS` | `60` | Polling cadence |

⚠️ The `INGEST_API_KEY` in `.env.example` is a **placeholder** — the real
key lives in the server's `.env` on the laptop. Copying the example
without replacing it caused a 401 debugging session on the Powerpal side
already; don't repeat it here.

## Run

```bash
cp .env.example .env        # fill in FRONIUS_HOST + INGEST_API_KEY
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python fronius-bridge.py
```

Readings print as they're posted; Ctrl+C stops cleanly.

### systemd

```ini
# /etc/systemd/system/fronius-bridge.service
[Unit]
Description=Fronius solar bridge -> home-energy-server
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/fronius-bridge
EnvironmentFile=/home/pi/fronius-bridge/.env
ExecStart=/home/pi/fronius-bridge/.venv/bin/python fronius-bridge.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Fronius Solar API hints

Most Fronius inverters (Gen24, Symo, Primo, Eco…) expose an unauthenticated
JSON API on the home LAN:

- Real-time power flow:
  `http://<FRONIUS_HOST>/solar_api/v1/GetPowerFlowRealtimeData.fjson`
- `Body.Data.Site.PAC` = current AC output in watts (per-string values in
  `P_PV*` fields)
- Poll it and post the value as `average_watts` — endpoint names can vary
  slightly by model/firmware, so confirm against your unit.

## Reference & credits

- [home-energy-server](https://github.com/benedict-chng/home-energy-server) — the server this feeds
- [powerpal-bridge](https://github.com/benedict-chng/powerpal-bridge) — the grid-side sibling bridge
