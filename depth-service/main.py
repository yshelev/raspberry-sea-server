import serial
import pynmea2
import redis
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Подключения
r = redis.Redis(host='redis', port=6378, decode_responses=True)
ser = serial.Serial('/dev/serial0', 4800, timeout=1)

logger.info("Глубинометр запущен")

while True:
    try:
        line = ser.readline().decode('ascii', errors='replace').strip()
        
        if line.startswith('$SDDPT') or line.startswith('$SDDBT'):
            msg = pynmea2.parse(line)
            
            if isinstance(msg, pynmea2.DPT):
                data = {
                    'depth_m': float(msg.depth_meters) if msg.depth_meters else 0,
                    'offset': float(msg.offset) if hasattr(msg, 'offset') else 0,
                    'timestamp': time.time()
                }
                r.hset('depth', mapping=data)
                r.set('depth:last', json.dumps(data))
                logger.info(f"Глубина: {data['depth_m']} м")
                
            elif isinstance(msg, pynmea2.DBT):
                data = {
                    'depth_m': float(msg.depth_meters) if msg.depth_meters else 0,
                    'depth_ft': float(msg.depth_feet) if msg.depth_feet else 0,
                    'timestamp': time.time()
                }
                r.hset('depth', mapping=data)
                r.set('depth:last', json.dumps(data))
                logger.info(f"Глубина: {data['depth_m']} м")
                
    except Exception as e:
        pass
        
    time.sleep(0.1)