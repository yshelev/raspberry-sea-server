from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis.asyncio as redis
import asyncio
import os
import json
import logging

from services.weather_service import fetch_wind_at_point
from services.wind_service import WindProcessor
from services.polar_map_service import PolarMapService
from services.png_websocket_service import PNGWebsocketService
from services.data_websocket_service import DataWebsocketService
from services.ai_service import compute_ai_route

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

png_websocket_service = PNGWebsocketService()
data_websocket_service = DataWebsocketService()
wind_service = WindProcessor()
polar_map_service = PolarMapService()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

clients = []
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

_latest_sensor_data = {
    "wind_twd": 90.0,
    "wind_tws": 12.0,
    "gps_lat":  43.109061,
    "gps_lon":  131.865189,
}


@app.on_event("startup")
async def startup():
    app.state.redis = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    asyncio.create_task(redis_listener())
    logger.info(f"Started Redis listener on {REDIS_HOST}:6379")


async def redis_listener():
    try:
        pubsub = app.state.redis.pubsub()
        await pubsub.subscribe("gps", "lag", "wind", "depth", "true_wind")
        logger.info("Subscribed to GPS, Lag and Wind channels")

        async for message in pubsub.listen():
            if message["type"] == "message":
                channel = message["channel"]
                raw_data = message["data"]

                try:
                    data = json.loads(raw_data)
                    if "depth_m" in data:
                        polar_map_service.initialize(data["depth_m"])
                except:
                    data = raw_data

                if channel == "true_wind" and isinstance(data, dict):
                    if "twd" in data:
                        _latest_sensor_data["wind_twd"] = data["twd"]
                    if "tws" in data:
                        _latest_sensor_data["wind_tws"] = data["tws"]
                elif channel == "gps" and isinstance(data, dict):
                    if "lat" in data:
                        _latest_sensor_data["gps_lat"] = data["lat"]
                    if "lon" in data:
                        _latest_sensor_data["gps_lon"] = data["lon"]

                payload = {"type": channel, "data": data}
                is_ok, err = await data_websocket_service.send_data(payload)
                logger.info(str(is_ok) + f"{err} PAYLOAD SENDED")

                true_wind_data = wind_service.update_data(channel, data)
                if not true_wind_data:
                    continue

                polar_map_service.set_module("tws", true_wind_data["tws"])
                polar_map_service.set_module("twa", true_wind_data["twa"])
                polar_map_service.set_module("boat_speed", true_wind_data["boat_speed"])

                is_polar_update_needed, save_path = await polar_map_service.add_field()
                if is_polar_update_needed:
                    is_ok, err = await png_websocket_service.send_data(
                        {"image_path": save_path}
                    )

                payload = {"type": "true_wind", "data": true_wind_data}
                is_ok, err = await data_websocket_service.send_data(payload)
                logger.info(str(is_ok) + f"{err} PAYLOAD SENDED")

    except Exception as e:
        logger.error(f"Redis listener error: {e}")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    data_websocket_service.add_to_clients(ws)
    logger.info(f"Client connected. Total clients: {len(clients)}")
    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=60.0)
                logger.info(f"Received from client: {data}")
            except asyncio.TimeoutError:
                continue
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if ws in clients:
            data_websocket_service.remove_client(ws)
        logger.info(f"Client disconnected. Total clients: {len(clients)}")


@app.websocket("/polar")
async def polar_websocket_endpoint(ws: WebSocket):
    await ws.accept()
    png_websocket_service.add_to_clients(ws)
    logger.info(f"Client connected. Total clients: {len(clients)}")
    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=60.0)
                logger.info(f"Received from client: {data}")
            except asyncio.TimeoutError:
                continue
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if ws in clients:
            png_websocket_service.remove_client(ws)
        logger.info(f"Client disconnected. Total clients: {len(clients)}")

@app.get("/")
async def root():
    return RedirectResponse(url="/map")

@app.get("/ws", response_class=HTMLResponse)
async def serve_ws():
    with open("static/ws.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/map", response_class=HTMLResponse)
async def serve_map():
    with open("static/map.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/polar-view", response_class=HTMLResponse)
async def serve_polar_viewer():
    with open("static/polar.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/wind", response_class=HTMLResponse)
async def serve_wind():
    with open("static/wind.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/data", response_class=HTMLResponse)
async def serve_data():
    with open("static/data.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/wind")
async def get_wind(lat: float, lon: float):
    return await fetch_wind_at_point(lat, lon)


class AIRouteRequest(BaseModel):
    checkpoints: list[dict]   # [{"lat": float, "lon": float}, ...]
    wind_twd: float | None = None 
    wind_tws: float | None = None


@app.get("/api/ai-debug")
async def ai_debug():
    import os
    from pathlib import Path
    from services.ai_service import AI_NAV_DIR, _net, _land_mask, _loaded, _ensure_loaded

    _ensure_loaded()

    cwd = Path.cwd()
    candidates = [
        cwd / "ai_navigation",
        cwd.parent / "ai_navigation",
        Path(__file__).parent.parent / "ai_navigation",
        Path(__file__).parent / "ai_navigation",
    ]

    return {
        "cwd": str(cwd),
        "main_py_location": str(Path(__file__).resolve()),
        "AI_NAV_DIR": str(AI_NAV_DIR),
        "net_loaded": _net is not None,
        "mask_loaded": _land_mask is not None,
        "candidates_exist": {str(c): (c / "best_network.json").exists() for c in candidates},
        "env_vars": {k: v for k, v in os.environ.items() if "path" in k.lower() or "dir" in k.lower()},
    }


@app.post("/api/ai-route")
async def get_ai_route(req: AIRouteRequest):
    wind_twd = req.wind_twd if req.wind_twd is not None else _latest_sensor_data["wind_twd"]
    wind_tws = req.wind_tws if req.wind_tws is not None else _latest_sensor_data["wind_tws"]
    start_lat = _latest_sensor_data["gps_lat"]
    start_lon = _latest_sensor_data["gps_lon"]

    logger.info(
        f"AI route request: {len(req.checkpoints)} checkpoints, "
        f"wind={wind_tws:.1f}kn@{wind_twd:.0f}°, "
        f"start=({start_lat:.4f},{start_lon:.4f})"
    )

    result = await compute_ai_route(
        checkpoints=req.checkpoints,
        start_lat=start_lat,
        start_lon=start_lon,
        wind_twd=wind_twd,
        wind_tws=wind_tws,
    )

    logger.info(
        f"AI route result: {result.get('checkpoints_reachable')}/{result.get('total_checkpoints')} cp, "
        f"time={result.get('estimated_time_min')}min"
    )

    return result
