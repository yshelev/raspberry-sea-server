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

logger.info("Ветрочет запущен")

while True:
    try:
        line = ser.readline().decode('ascii', errors='replace').strip()
        
        if line.startswith('$WIMWV') or line.startswith('$IIMWV'):
            msg = pynmea2.parse(line)
            
            if isinstance(msg, pynmea2.MWV):
                wind_speed = float(msg.wind_speed) if msg.wind_speed else 0
                wind_units = msg.wind_speed_units if hasattr(msg, 'wind_speed_units') else 'N'
                
                speed_knots = wind_speed if wind_units == 'N' else wind_speed / 1.852
                speed_ms = wind_speed if wind_units == 'M' else wind_speed * 0.514444
                
                data = {
                    'angle': float(msg.wind_angle) if msg.wind_angle else 0,
                    'speed_knots': round(speed_knots, 1),
                    'speed_ms': round(speed_ms, 1),
                    'speed_raw': wind_speed,
                    'units': wind_units,
                    'timestamp': time.time()
                }
                
                r.hset('wind', mapping=data)
                r.set('wind:last', json.dumps(data))
                logger.info(f"Ветер: {data['angle']}°, {data['speed_knots']} узлов")
                
    except Exception as e:
        pass
        
    time.sleep(0.1)