from fastapi import FastAPI, WebSocket
import redis.asyncio as redis
import asyncio
import os

app = FastAPI()

clients = []
REDIS_HOST = os.getenv("REDIS_HOST", "redis")


@app.on_event("startup")
async def startup():
    app.state.redis = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    asyncio.create_task(redis_listener())


async def redis_listener():
    pubsub = app.state.redis.pubsub()
    await pubsub.subscribe("gps")

    async for message in pubsub.listen():
        if message["type"] == "message":
            data = message["data"]

            # рассылаем всем клиентам
            for ws in clients:
                try:
                    await ws.send_text(data)
                except:
                    pass


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)

    try:
        while True:
            await ws.receive_text()
    except:
        clients.remove(ws)