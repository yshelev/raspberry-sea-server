import time
import logging
import os
import json
import redis
import math
from datetime import datetime

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

WAYPOINTS = [
    {"lat": 43.15893822833752, "lon": 131.87746628229846},   # Исправлено: lat, lon
    {"lat": 43.13229055069301, "lon": 131.84931381647814},
    {"lat": 43.107140507737114, "lon": 131.86339004938824},
    {"lat": 43.08336414876978, "lon": 131.8399868746787},
    {"lat": 43.07480741724592, "lon": 131.8523464938193},
    {"lat": 43.11053637145254, "lon": 131.87603576383884},
    {"lat": 43.15893822833752, "lon": 131.87746628229846},   # Замыкаем маршрут
]

# Параметры движения
SPEED_KT = 400  # Скорость в узлах (1 узел = 1.852 км/ч)
UPDATE_INTERVAL = 1  # Интервал обновления в секундах (как в старом коде)

def calculate_distance(lat1, lon1, lat2, lon2):
    """Вычисляет расстояние между двумя точками в километрах"""
    R = 6371  # Радиус Земли в км
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * \
        math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Вычисляет азимут от точки 1 к точке 2"""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - \
        math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
    
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360

def interpolate_position(lat1, lon1, lat2, lon2, fraction):
    """Интерполирует позицию между двумя точками"""
    lat = lat1 + (lat2 - lat1) * fraction
    lon = lon1 + (lon2 - lon1) * fraction
    return lat, lon

class GPSSimulator:
    def __init__(self, waypoints, speed_kts=10, update_interval=1):
        self.waypoints = waypoints
        self.speed_kts = speed_kts
        self.speed_kmh = speed_kts * 1.852  # Конвертация узлов в км/ч (для совместимости)
        self.update_interval = update_interval
        self.current_waypoint_index = 0
        self.current_position = {
            "lat": waypoints[0]["lat"],
            "lon": waypoints[0]["lon"]
        }
        self.current_track = 0
        self.last_time = time.time()
        
        logger.info(f"GPS Simulator started: lat={self.current_position['lat']}, "
                   f"lon={self.current_position['lon']}, "
                   f"speed={self.speed_kmh} km/h, track={self.current_track}°")
        
    def update(self):
        """Обновляет позицию и возвращает данные в формате как у старого эмулятора"""
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        
        # Обновляем позицию по маршруту
        self.update_position()
        
        return self.get_data()
    
    def update_position(self):
        """Обновляет позицию на основе текущего маршрута"""
        # Текущая цель
        target = self.waypoints[self.current_waypoint_index]
        
        # Расстояние до следующей точки
        distance_to_target = calculate_distance(
            self.current_position["lat"], 
            self.current_position["lon"],
            target["lat"], 
            target["lon"]
        )
        
        # Расстояние, которое проходим за один шаг (в км)
        step_distance = self.speed_kmh * self.update_interval / 3600  # км за шаг
        
        # Рассчитываем курс на целевую точку
        self.current_track = calculate_bearing(
            self.current_position["lat"],
            self.current_position["lon"],
            target["lat"],
            target["lon"]
        )
        
        if step_distance >= distance_to_target:
            # Достигли точки, переключаемся на следующую
            self.current_position = {
                "lat": target["lat"],
                "lon": target["lon"]
            }
            self.current_waypoint_index = (self.current_waypoint_index + 1) % len(self.waypoints)
            
            # Рекурсивно обновляем позицию, если нужно пройти дальше
            remaining_distance = step_distance - distance_to_target
            if remaining_distance > 0 and remaining_distance < step_distance:
                self.update_position()
        else:
            # Двигаемся к следующей точке
            fraction = step_distance / distance_to_target
            
            new_lat, new_lon = interpolate_position(
                self.current_position["lat"], 
                self.current_position["lon"],
                target["lat"], 
                target["lon"],
                fraction
            )
            
            self.current_position = {
                "lat": new_lat,
                "lon": new_lon
            }
    
    def get_data(self):
        """Возвращает данные в том же формате, что и старый эмулятор"""
        return {
            "time": datetime.now().isoformat(),
            "timestamp": time.time(),
            "lat": round(self.current_position["lat"], 6),
            "lon": round(self.current_position["lon"], 6),
            "speed_kmh": round(self.speed_kmh, 2),
            "track": round(self.current_track, 2),
        }

# Создаем симулятор
gps = GPSSimulator(WAYPOINTS, SPEED_KT, UPDATE_INTERVAL)

logger.info(f"Starting GPS simulation with {len(WAYPOINTS)} waypoints")
logger.info(f"Speed: {SPEED_KT} knots ({SPEED_KT * 1.852:.1f} km/h)")
logger.info("Publishing to Redis...")

counter = 0

try:
    while True:
        data = gps.update()
        
        try:
            r.publish("gps", json.dumps(data))
            counter += 1
            
            if counter % 10 == 0:  # Логируем каждые 10 секунд
                logger.info(f"GPS: lat={data['lat']:.6f}, lon={data['lon']:.6f}, "
                           f"speed={data['speed_kmh']:.1f} km/h, track={data['track']:.1f}°")
        except Exception as e:
            logger.error(f"Redis error: {e}")
        
        time.sleep(UPDATE_INTERVAL)
        
except KeyboardInterrupt:
    logger.info("GPS emulator stopped")
    
finally:
    try:
        r.publish("gps", json.dumps({"status": "shutdown"}))
    except:
        pass