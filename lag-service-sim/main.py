import time
import logging
import random
import os
import redis
import json
from datetime import datetime


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LagEmulator:
    def __init__(self):
        self.speed_knots = 5.0
        self.total_distance = 1000
        self.trip_distance = 0.0
        self.last_time = time.time()
        self.target_speed = 5.0


    def update(self):
        now = time.time()
        dt = now - self.last_time
        self.last_time = now

        if random.random() < 0.08:
            self.target_speed += random.uniform(-4, 4)
            self.target_speed = max(0, min(15, self.target_speed))

        self.speed_knots += (self.target_speed - self.speed_knots) * 0.03

        distance = self.speed_knots * dt / 3600

        self.total_distance += distance
        self.trip_distance += distance

        return self.get_data()


    def get_data(self):
        return {
            "timestamp": time.time(), 
            "time": datetime.now().isoformat(),
            "speed_knots": round(self.speed_knots, 2),
            "speed_kmh": round(self.speed_knots * 1.852, 2),
            "total_distance_nm": round(self.total_distance, 3),
            "trip_distance_nm": round(self.trip_distance, 3),
        }

def main():

    lag = LagEmulator()
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()

        r.publish("lag", json.dumps({"status": "startup"}))

    except Exception as e:
        return

    counter = 0

    try:
        while True:
            data = lag.update()

            r.publish("lag", json.dumps(data))

            counter += 1

            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Stopping Lag Emulator")

    finally:
        try:
            r.publish("lag", json.dumps({"status": "shutdown"}))
        except:
            pass


if __name__ == "__main__":
    main()




