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

`fronius-bridge.py` is intentionally empty for now — being implemented by
hand. The server-side contract above is live and proven (ingest tested
end-to-end); only the inverter-reading + posting logic needs filling in.

## Planned configuration (.env, mirrors powerpal-bridge)

| Variable | Example | Purpose |
|----------|---------|---------|
| `FRONIUS_HOST` | `192.168.68.x` | Fronius inverter IP on the home LAN |
| `INGEST_URL` | `http://192.168.68.141:8000/api/v1/solar/readings` | Solar ingest endpoint |
| `INGEST_API_KEY` | — | The server's ingest API key (same key as powerpal-bridge) |
| `POLL_SECONDS` | `60` | Polling cadence |

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
