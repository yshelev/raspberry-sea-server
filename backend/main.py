import asyncpg
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import asyncio
import os
import json
import logging
from services.wind_service import WindProcessor
from services.polar_map_service import PolarMapService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

wind_service = WindProcessor()
polarMapService = PolarMapService()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
                logger.info(f"[123] {message}")
                channel = message["channel"]
                raw_data = message["data"]

                # logger.info(f"[{channel}] {raw_data[:100]}")

                try:
                    data = json.loads(raw_data)
                except:
                    data = raw_data

                payload = {
                    "type": channel,
                    "data": data
                }

                for ws in clients[:]:
                    try:
                        await ws.send_text(json.dumps(payload))
                    except Exception as e:
                        logger.error(f"Error sending to client: {e}")
                        if ws in clients:
                            clients.remove(ws)

                true_wind_data = wind_service.update_data(channel, data)
                if not true_wind_data:
                    continue

                payload = {
                    "type": "true_wind",
                    "data": true_wind_data
                }

                for ws in clients[:]:
                    try:
                        await ws.send_text(json.dumps(payload))
                    except Exception as e:
                        logger.error(f"Error sending to client: {e}")
                        if ws in clients:
                            clients.remove(ws)

    except Exception as e:
        logger.error(f"Redis listener error: {e}")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    logger.info(f"Client connected. Total clients: {len(clients)}")

    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=60.0)
                logger.info(f"Received from client: {data}")

                await ws.send_text(json.dumps({"status": "ok", "message": "received"}))
            except asyncio.TimeoutError:
                continue

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if ws in clients:
            clients.remove(ws)
        logger.info(f"Client disconnected. Total clients: {len(clients)}")


@app.get("/")
async def root():
    return {"message": "GPS Server is running", "clients": len(clients)}


@app.get("/health")
async def health():
    return {"status": "ok", "clients": len(clients)}

