import time
import json
import redis
import random
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wind-service-sim")


class WindEmulator:

    def __init__(self):
        self.aws = 10.0  # apparent wind speed
        self.awa = 90  # apparent wind angle
        self.target_awa = 90

    def update(self):
        wind_gust = random.uniform(-1.2, 1.2)
        self.aws += wind_gust
        self.aws = max(0, self.aws)

        if random.random() < 0.03:
            self.target_awa = random.uniform(30, 170)

        self.awa += (self.target_awa - self.awa) * 0.1
        self.awa += random.uniform(-3, 3)
        self.awa = max(0, min(180, self.awa))

    def read(self):
        self.update()

        return {
            "timestamp": time.time(), 
            "time": datetime.now().isoformat(),
            "aws": round(self.aws, 2),
            "awa": round(self.awa),
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