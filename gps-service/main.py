from gps3 import gps3
import time
import os
import json
import redis

GPS_HOST = os.getenv("GPS_HOST", "gpsd")
GPS_PORT = int(os.getenv("GPS_PORT", 2947))
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

gps_socket = gps3.GPSDSocket()
data_stream = gps3.DataStream()

gps_socket.connect(host=GPS_HOST, port=GPS_PORT)
gps_socket.watch()


for new_data in gps_socket:
    if True: # new_data
        try:
            data_stream.unpack(new_data)
            tpv = data_stream.TPV
        except Exception as e: 
            tpv = {
                "time": 1,
                "lat": 1,
                "lon": 1,
                "alt": 1,
                "speed": 1,
                "track": 1,
            }
        payload = {
            "time": tpv.get("time"),
            "lat": tpv.get("lat"),
            "lon": tpv.get("lon"),
            "alt": tpv.get("alt"),
            "speed": tpv.get("speed"),
            "track": tpv.get("track"),
        }

        try:
            r.publish("gps", json.dumps(payload))
        except Exception as e:
            print("Redis error:", e)

        time.sleep(0.5)