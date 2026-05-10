import json
import math
import time
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("wind processor")

MAX_TIME_DELTA = 2.0  # сек


class WindProcessor:
    def __init__(self):
        logger.info("qweqrwq")
        self.latest = {
            "gps": None,
            "lag": None,
            "wind": None
        }

    def normalize_angle(self, angle):
        """
        Приводим угол к диапазону [-180, 180]
        """
        return (angle + 180) % 360 - 180

    def is_synced(self):
        """
        Проверяем что все данные достаточно свежие
        """
        logger.info(json.dumps(self.latest))

        if not all(self.latest.values()):
            return False

        timestamps = [
            self.latest["gps"]["timestamp"],
            self.latest["lag"]["timestamp"],
            self.latest["wind"]["timestamp"]
        ]

        return max(timestamps) - min(timestamps) <= MAX_TIME_DELTA

    def update_data(self, key, data): 
        logger.info(f"{key} {data}")
        logger.info(json.dumps(self.latest))
        if self.latest.get(key, -1) == -1: 
            return 
        
        self.latest[key] = data
        if self.is_synced(): 
            return self.calculate_true_wind()

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
            "twd": round(true_wind_direction, 2),
            "boat_speed": round(boat_speed, 2),
        }