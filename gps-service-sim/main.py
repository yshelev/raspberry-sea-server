import math
import time
import logging
from datetime import datetime
import os
import redis 
import json 

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class GPSEmulator:
    def __init__(self, start_lat=55.7558, start_lon=37.6176):
        self.lat = start_lat      # начальная широта (Москва)
        self.lon = start_lon      # начальная долгота
        self.alt = 150            # высота
        self.speed = 50           # скорость км/ч
        self.track = 90           # курс на восток
        self.last_time = time.time()
        
        logger.info(f"GPS Emulator initialized at position: lat={self.lat}, lon={self.lon}, "
                   f"alt={self.alt}, speed={self.speed} km/h, track={self.track}°")
    
    def update_position(self):
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time
        
        logger.debug(f"Time delta: {dt:.3f} seconds")
        
        # Перемещение в зависимости от скорости и времени
        distance = (self.speed * 1000 / 3600) * dt  # метры
        logger.debug(f"Distance traveled: {distance:.2f} meters")
        
        # Преобразование курса в радианы
        track_rad = math.radians(self.track)
        logger.debug(f"Track angle: {self.track}° ({track_rad:.4f} rad)")
        
        # Изменение координат (приблизительно)
        # 1 градус широты ≈ 111 км
        # 1 градус долготы ≈ 111 * cos(широта) км
        lat_change = (distance * math.cos(track_rad)) / 111000
        lon_change = (distance * math.sin(track_rad)) / (111000 * math.cos(math.radians(self.lat)))
        
        old_lat, old_lon = self.lat, self.lon
        
        self.lat += lat_change
        self.lon += lon_change
        
        logger.debug(f"Position change: Δlat={lat_change:.6f}°, Δlon={lon_change:.6f}°")
        logger.debug(f"New position: lat={self.lat:.6f}°, lon={self.lon:.6f}°")
        
        return self.get_tpv()
    
    def get_tpv(self):
        return {
            "time": datetime.now().isoformat(),
            "timestamp": datetime.now().timestamp(),
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "alt": self.alt,
            "speed": self.speed,
            "track": self.track,
        }
    
    def set_speed(self, speed):
        old_speed = self.speed
        self.speed = speed
        logger.info(f"Speed changed: {old_speed} km/h → {self.speed} km/h")
    
    def set_track(self, track):
        old_track = self.track
        self.track = track
        logger.info(f"Track changed: {old_track}° → {self.track}°")

def main():
    logger.info("Starting GPS Emulator Service")
    
    # Инициализация GPS эмулятора
    gps = GPSEmulator()
    
    # Подключение к Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    
    logger.info(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")
    
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        
        # Проверка соединения с Redis
        r.ping()
        logger.info("Successfully connected to Redis")
        
        # Тестовая публикация для проверки
        test_data = {"status": "startup", "message": "GPS Emulator started"}
        r.publish("gps", json.dumps(test_data))
        logger.info("Published startup message to GPS channel")
        
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        logger.error(f"Make sure Redis is running at {REDIS_HOST}:{REDIS_PORT}")
        return
    except Exception as e:
        logger.error(f"Unexpected error connecting to Redis: {e}")
        return
    
    # Счетчик публикаций
    publish_count = 0
    
    try:
        while True:
            try:
                # Получение GPS данных
                data = gps.update_position()
                
                # Публикация в Redis
                json_data = json.dumps(data)
                r.publish("gps", json_data)
                
                publish_count += 1
                
                # Логирование отправленных данных
                logger.info(f"[#{publish_count}] Published GPS data: "
                           f"lat={data['lat']:.6f}, lon={data['lon']:.6f}, "
                           f"speed={data['speed']} km/h, track={data['track']}°")
                
                # Для отладки - полные данные
                logger.debug(f"Full GPS data: {json_data}")
                
                # Задержка между публикациями
                time.sleep(1)
                
                # Демонстрация изменения курса каждые 30 секунд
                if publish_count % 30 == 0:
                    new_track = (gps.track + 10) % 360
                    gps.set_track(new_track)
                
                # Демонстрация изменения скорости каждые 60 секунд
                if publish_count % 60 == 0:
                    new_speed = (gps.speed + 5) % 100
                    gps.set_speed(new_speed)
                    
            except redis.ConnectionError as e:
                logger.error(f"Redis connection lost: {e}")
                logger.info("Attempting to reconnect...")
                time.sleep(5)
                continue
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(1)
                continue
                
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        logger.info(f"Total messages published: {publish_count}")
        logger.info("GPS Emulator stopped")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        try:
            # Публикация сообщения о завершении работы
            shutdown_data = {"status": "shutdown", "total_messages": publish_count}
            r.publish("gps", json.dumps(shutdown_data))
            logger.info("Published shutdown message")
        except:
            pass

if __name__ == "__main__":
    main()