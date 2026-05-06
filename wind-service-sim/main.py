import time
import json
import redis
import random
import math
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wind-service-sim")


class WindEmulator:

    def __init__(self):
        self.aws = 10.0  # apparent wind speed
        self.awa = 0.0   # apparent wind angle

    def update(self):
        # турбулентность ветра
        wind_gust = random.uniform(-1.2, 1.2)

        self.aws += wind_gust
        self.aws = max(0, self.aws)

        # флюгер гуляет
        self.awa += random.uniform(-6, 6)

        # нормализация угла (-180..180)
        if self.awa > 180:
            self.awa -= 360
        elif self.awa < -180:
            self.awa += 360

    def read(self):
        self.update()

        return {
            "timestamp": time.time(), 
            "time": datetime.now().isoformat(),
            "aws": round(self.aws, 2),
            "awa": round(self.awa, 2),
            "status": "ok"
        }


def main():
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True
    )

    wind = WindEmulator()

    counter = 0


    while True:
        try:
            data = wind.read()

            r.publish("wind", json.dumps(data))

            counter += 1

            time.sleep(1)

        except Exception as e:
            time.sleep(1)


if __name__ == "__main__":
    main()