import time
import logging
import random
import os
import math
import redis
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def compute_tws_twa(aws: float, awa_deg: float, boat_speed: float) -> tuple[float, float]:
    """
    Считаем истинный ветер из вымпельного и скорости лодки.
    Возвращает (TWS, TWA) в узлах и градусах (не берем TWS и TWA из wind_processor,
    чтобы не делать дополнительной логики на бекенде).
    """
    awa_rad = math.radians(awa_deg)

    aw_x = aws * math.sin(awa_rad)
    aw_y = aws * math.cos(awa_rad)

    boat_y = boat_speed

    tw_x = aw_x
    tw_y = aw_y - boat_y

    tws = math.sqrt(tw_x**2 + tw_y**2)
    twa = math.degrees(math.atan2(tw_x, tw_y)) % 360

    return tws, twa


def wind_speed_factor(twa: float, tws: float) -> float:
    """
    Коэффициент влияния ветра на скорость лодки.

    Полный бейдевинд (~45°) и галфвинд (90°) — лучшие курсы для парусника.
    Фордевинд (180°) — медленнее. В мёртвый бейдевинд (0°) — не идём.

    Возвращает target_speed в узлах.
    """
    DEAD_ZONE = 30

    angle = twa if twa <= 180 else 360 - twa

    if angle < DEAD_ZONE:
        return 0.5

    if angle < 60:
        efficiency = (angle - DEAD_ZONE) / (60 - DEAD_ZONE)
    elif angle <= 130:
        efficiency = 1.0
    else:
        efficiency = 1.0 - 0.4 * (angle - 130) / 50

    efficiency = max(0.1, efficiency)

    max_boat_speed = min(tws * 0.9, 15.0)

    return round(max_boat_speed * efficiency, 2)


class LagEmulator:
    def __init__(self):
        self.speed_knots = 5.0
        self.total_distance = 1000.0
        self.trip_distance = 0.0
        self.last_time = time.time()
        self.target_speed = 5.0

        self.latest_wind: dict | None = None

    def apply_wind(self, aws: float, awa: float):
        """Принимаем вымпельный ветер, считаем target_speed через TWS/TWA."""
        tws, twa = compute_tws_twa(aws, awa, self.speed_knots)
        self.target_speed = wind_speed_factor(twa, tws)
        logger.debug(f"TWS={tws:.1f} TWA={twa:.0f}° → target={self.target_speed:.1f} kn")

    def update(self):
        now = time.time()
        dt = now - self.last_time
        self.last_time = now

        if self.latest_wind:
            self.apply_wind(self.latest_wind["aws"], self.latest_wind["awa"])
        else:
            if random.random() < 0.08:
                self.target_speed += random.uniform(-4, 4)
                self.target_speed = max(0, min(15, self.target_speed))

        self.speed_knots += (self.target_speed - self.speed_knots) * 0.03
        self.speed_knots = max(0.0, self.speed_knots)

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
        logger.error(f"Redis connection failed: {e}")
        return

    pubsub = r.pubsub()
    pubsub.subscribe("wind")

    try:
        while True:
            message = pubsub.get_message(ignore_subscribe_messages=True)
            while message:
                try:
                    wind_data = json.loads(message["data"])
                    if "aws" in wind_data and "awa" in wind_data:
                        lag.latest_wind = wind_data
                except (json.JSONDecodeError, KeyError):
                    pass
                message = pubsub.get_message(ignore_subscribe_messages=True)

            data = lag.update()
            r.publish("lag", json.dumps(data))

            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Stopping Lag Emulator")
    finally:
        try:
            r.publish("lag", json.dumps({"status": "shutdown"}))
        except:
            pass
        pubsub.close()


if __name__ == "__main__":
    main()