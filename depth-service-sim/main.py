import time
import logging
import random
import os
import redis
import json
from datetime import datetime
import math


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("depth-sim")


class DepthEmulator:
    def __init__(self):
        # базовая глубина (например море)
        self.base_depth = 25.0

        # шум волн
        self.wave_phase = 0.0

        logger.info("Depth emulator started")

    def update(self):
        # волновая модель (очень упрощённая)
        self.wave_phase += 0.1

        wave = math.sin(self.wave_phase) * 1.5

        noise = random.uniform(-0.2, 0.2)

        depth = self.base_depth + wave + noise

        return {
            "time": datetime.now().isoformat(),
            "timestamp": time.time(),
            "depth_m": round(depth, 2),
            "status": "ok"
        }


def main():
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()

    depth = DepthEmulator()

    counter = 0

    try:
        while True:
            data = depth.update()

            r.publish("depth", json.dumps(data))

            counter += 1

            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Depth emulator stopped")

    finally:
        try:
            r.publish("depth", json.dumps({"status": "shutdown"}))
        except:
            pass


if __name__ == "__main__":
    main()