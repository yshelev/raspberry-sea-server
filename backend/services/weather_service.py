import httpx
import logging

logger = logging.getLogger(__name__)

async def fetch_wind_at_point(lat: float, lon: float) -> dict:
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=wind_speed_10m,wind_direction_10m"
        f"&wind_speed_unit=ms"
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            logger.info(f"Open-Meteo [{lat},{lon}] status: {resp.status_code}")
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Open-Meteo [{lat},{lon}] response: {data}")
            current = data["current"]
            return {
                "lat": lat,
                "lon": lon,
                "speed": current["wind_speed_10m"],
                "dir": current["wind_direction_10m"]
            }
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error [{lat},{lon}]: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error [{lat},{lon}]: {type(e).__name__}: {e}")
        raise