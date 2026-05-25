import serial
import pynmea2
import redis
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

r = redis.Redis(host='redis', port=6378, decode_responses=True)
ser = serial.Serial('/dev/serial0', 4800, timeout=1)

logger.info("Лаг запущен")

while True:
    try:
        line = ser.readline().decode('ascii', errors='replace').strip()
        
        if line.startswith('$IIVHW') or line.startswith('$GPRMC'):
            msg = pynmea2.parse(line)
            
            if isinstance(msg, pynmea2.VHW):
                data = {
                    'speed_knots': float(msg.speed_knots) if msg.speed_knots else 0,
                    'speed_kmh': float(msg.speed_kph) if msg.speed_kph else 0,
                    'heading': float(msg.heading_degrees) if msg.heading_degrees else 0,
                    'timestamp': time.time()
                }
                r.hset('speed', mapping=data)
                r.set('speed:last', json.dumps(data))
                logger.info(f"Скорость: {data['speed_knots']} узлов ({data['speed_kmh']} км/ч)")
                
            elif isinstance(msg, pynmea2.RMC):
                data = {
                    'speed_knots': float(msg.spd_over_grnd) if msg.spd_over_grnd else 0,
                    'speed_kmh': float(msg.spd_over_grnd) * 1.852 if msg.spd_over_grnd else 0,
                    'course': float(msg.true_course) if msg.true_course else 0,
                    'timestamp': time.time()
                }
                r.hset('speed', mapping=data)
                r.set('speed:last', json.dumps(data))
                logger.info(f"Скорость: {data['speed_knots']} узлов")
                
    except Exception as e:
        pass
        
    time.sleep(0.1)