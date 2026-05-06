import redis
import json
import math
import os
import time
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("wind-processor")


REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

MAX_TIME_DELTA = 2.0  # сек


class WindProcessor:
    def __init__(self):
        self.latest = {
            "gps": None,
            "lag": None,
            "wind": None
        }

        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True
        )

        self.pubsub = self.redis.pubsub()

    def subscribe(self):
        self.pubsub.subscribe("gps", "lag", "wind")
        logger.info("Subscribed to gps, lag, wind channels")

    def normalize_angle(self, angle):
        """
        Приводим угол к диапазону [-180, 180]
        """
        return (angle + 180) % 360 - 180

    def is_synced(self):
        """
        Проверяем что все данные достаточно свежие
        """
        if not all(self.latest.values()):
            return False

        timestamps = [
            self.latest["gps"]["timestamp"],
            self.latest["lag"]["timestamp"],
            self.latest["wind"]["timestamp"]
        ]

        return max(timestamps) - min(timestamps) <= MAX_TIME_DELTA

    def calculate_true_wind(self):
        gps = self.latest["gps"]
        lag = self.latest["lag"]
        wind = self.latest["wind"]

        aws = wind["aws"]                # apparent wind speed
        awa = wind["awa"]                # apparent wind angle
        boat_speed = lag["speed_knots"]  # лучше брать лаг
        heading = gps["track"]           # курс лодки

        awa_rad = math.radians(awa)

        # apparent wind vector
        aw_x = aws * math.sin(awa_rad)
        aw_y = aws * math.cos(awa_rad)

        # boat vector
        boat_x = 0
        boat_y = boat_speed

        # true wind vector
        tw_x = aw_x + boat_x
        tw_y = aw_y + boat_y

        tws = math.sqrt(tw_x**2 + tw_y**2)

        twa = math.degrees(math.atan2(tw_x, tw_y))
        twa = self.normalize_angle(twa)

        true_wind_direction = (heading + twa) % 360

        return {
            "timestamp": time.time(),
            "tws": round(tws, 2),
            "twa": round(twa, 2),
            "twd": round(true_wind_direction, 2)
        }

    def process_message(self, channel, data):
        try:
            parsed = json.loads(data)

            if "timestamp" not in parsed:
                logger.warning(f"{channel} missing timestamp")
                return

            self.latest[channel] = parsed

            logger.info(f"Updated {channel}")

            if self.is_synced():
                result = self.calculate_true_wind()

                self.redis.publish(
                    "true_wind",
                    json.dumps(result)
                )

                logger.info(
                    f"TWS={result['tws']} kn | "
                    f"TWA={result['twa']}° | "
                    f"TWD={result['twd']}°"
                )
            else:
                logger.info("Waiting for synchronized sensor data...")

        except Exception as e:
            logger.error(f"Processing error: {e}")

    def run(self):
        self.subscribe()

        logger.info("Wind processor started")

        for message in self.pubsub.listen():
            if message["type"] != "message":
                continue

            channel = message["channel"]
            data = message["data"]

            self.process_message(channel, data)


def main():
    try:
        processor = WindProcessor()
        processor.run()
    except KeyboardInterrupt:
        logger.info("Wind processor stopped")


if __name__ == "__main__":
    main()