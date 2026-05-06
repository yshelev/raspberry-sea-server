import time
import logging
import random
import os
import redis
import json
from datetime import datetime
import math


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GPSEmulator:
    def __init__(self, start_lat=55.7558, start_lon=37.6176):
        self.lat = start_lat
        self.lon = start_lon

        self.speed_kmh = 50.0
        self.track = 90.0

        self.last_time = time.time()

        logger.info(
            f"GPS Emulator started: "
            f"lat={self.lat}, lon={self.lon}, "
            f"speed={self.speed_kmh} km/h, track={self.track}°"
        )

    def update(self):
        now = time.time()
        dt = now - self.last_time
        self.last_time = now

        # лёгкий шум скорости и курса (как в реальном GPS)
        if random.random() < 0.05:
            self.speed_kmh += random.uniform(-2, 2)
            self.speed_kmh = max(0, self.speed_kmh)

        self.track += random.uniform(-1, 1)
        self.track %= 360

        # расстояние за dt
        distance = (self.speed_kmh * 1000 / 3600) * dt

        track_rad = math.radians(self.track)

        lat_change = (distance * math.cos(track_rad)) / 111000
        lon_change = (distance * math.sin(track_rad)) / (
            111000 * math.cos(math.radians(self.lat))
        )

        self.lat += lat_change
        self.lon += lon_change

        return self.get_data()

    def get_data(self):
        return {
            "time": datetime.now().isoformat(),
            "timestamp": time.time(),
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "speed_kmh": round(self.speed_kmh, 2),
            "track": round(self.track, 2),
        }


def main():
    logger.info("Starting GPS Emulator (clean version)")

    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()

    gps = GPSEmulator()

    counter = 0

    try:
        while True:
            data = gps.update()

            r.publish("gps", json.dumps(data))

            counter += 1

            logger.info(
                f"[#{counter}] "
                f"lat={data['lat']} lon={data['lon']} "
                f"speed={data['speed_kmh']} km/h "
                f"track={data['track']}°"
            )

            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("GPS emulator stopped")

    finally:
        try:
            r.publish("gps", json.dumps({"status": "shutdown"}))
        except:
            pass


if __name__ == "__main__":
    main()