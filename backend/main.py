from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import asyncio
import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        await pubsub.subscribe("gps")
        logger.info("Subscribed to GPS channel")
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                logger.info(f"Received GPS data: {data[:100]}")  # первые 100 символов
                
                for ws in clients[:]:
                    try:
                        await ws.send_text(data)
                        logger.debug(f"Sent to client: {data[:50]}")
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
            # Получаем сообщение от клиента с таймаутом
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=60.0)
                logger.info(f"Received from client: {data}")
                
                # Отправляем подтверждение
                await ws.send_text(json.dumps({"status": "ok", "message": "received"}))
            except asyncio.TimeoutError:
                # Таймаут - просто продолжаем слушать
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