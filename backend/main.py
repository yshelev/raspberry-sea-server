from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import asyncio
import os
import json
import logging
from services.wind_service import WindProcessor
from services.polar_map_service import PolarMapService
from services.png_websocket_service import PNGWebsocketService
from services.data_websocket_service import DataWebsocketService

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

@app.on_event("startup")
async def startup():
    app.state.redis = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    asyncio.create_task(redis_listener())
    logger.info(f"Started Redis listener on {REDIS_HOST}:6379")


async def redis_listener():
    try:
        pubsub = app.state.redis.pubsub()
        await pubsub.subscribe("gps", "lag", "wind", "depth", "true_wind")
        logger.info("Subscribed to GPS,Lag and Wind channels")

        async for message in pubsub.listen():
            if message["type"] == "message":
                # logger.info(f"[123] {message}")
                channel = message["channel"]
                raw_data = message["data"]

                # logger.info(f"[{channel}] {raw_data[:100]}")

                try:
                    data = json.loads(raw_data)
                    if "depth_m" in data:
                        polar_map_service.initialize(data["depth_m"])
                except:
                    data = raw_data

                payload = {
                    "type": channel,
                    "data": data
                }

                is_ok, err = await data_websocket_service.send_data(payload)
                logger.info(str(is_ok) + f"{err} PAYLOAD SENDED" )

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

                payload = {
                    "type": "true_wind",
                    "data": true_wind_data
                }

                is_ok, err = await data_websocket_service.send_data(payload)
                logger.info(str(is_ok) + f"{err} PAYLOAD SENDED" )
                
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
    return {"message": "GPS Server is running", "clients": len(clients)}

@app.get("/ws", response_class=HTMLResponse)
async def serve_map():
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
