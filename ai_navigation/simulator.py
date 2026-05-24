import json
import math
import numpy as np
from PIL import Image

CHECKPOINT_RADIUS_NM = 0.027
EARTH_RADIUS_NM      = 3440.065
MAX_TURN_RATE_DEG    = 15.0
DEAD_ZONE_DEG        = 30


class LandMask:

    def __init__(self, meta_path: str = "coastline.json"):
        with open(meta_path) as f:
            meta = json.load(f)

        import os
        mask_path = meta["mask_file"]
        if not os.path.exists(mask_path):
            base_dir = os.path.dirname(os.path.abspath(meta_path))
            mask_path = os.path.join(base_dir, os.path.basename(mask_path))

        self.geo  = meta["geo"]
        self.bbox = meta["bbox"]

        img = Image.open(mask_path).convert("L")
        self._mask = np.array(img, dtype=np.uint8)
        self._h, self._w = self._mask.shape

        g = self.geo
        self._lon_scale = self._w / (g["se_lon"] - g["nw_lon"])
        self._lat_scale = self._h / (g["nw_lat"] - g["se_lat"])
        self._nw_lon = g["nw_lon"]
        self._nw_lat = g["nw_lat"]

        water_pct = (self._mask > 128).mean() * 100
        print(f"LandMask: {self._w}×{self._h}px | вода {water_pct:.0f}% | "
              f"bbox ({self.bbox['min_lat']},{self.bbox['min_lon']}) → "
              f"({self.bbox['max_lat']},{self.bbox['max_lon']})")

    def is_land(self, lat: float, lon: float) -> bool:
        if not (self.bbox["min_lat"] <= lat <= self.bbox["max_lat"] and
                self.bbox["min_lon"] <= lon <= self.bbox["max_lon"]):
            return False
        col = int((lon - self._nw_lon) * self._lon_scale)
        row = int((self._nw_lat - lat) * self._lat_scale)
        col = max(0, min(col, self._w - 1))
        row = max(0, min(row, self._h - 1))
        return self._mask[row, col] < 128


class WindModel:

    def __init__(self, base_twd, base_tws,
                 twd_sigma=3.0, tws_sigma=0.5,
                 twd_alpha=0.03, tws_alpha=0.05,
                 tws_min=4.0, tws_max=30.0):
        self.base_twd = base_twd
        self.base_tws = base_tws
        self.twd_sigma = twd_sigma
        self.tws_sigma = tws_sigma
        self.twd_alpha = twd_alpha
        self.tws_alpha = tws_alpha
        self.tws_min = tws_min
        self.tws_max = tws_max
        self.twd = base_twd
        self.tws = base_tws

    def reset(self):
        self.twd = self.base_twd
        self.tws = self.base_tws

    def step(self) -> tuple[float, float]:
        twd_diff = (self.base_twd - self.twd + 180) % 360 - 180
        self.twd = (self.twd
                    + self.twd_alpha * twd_diff
                    + self.twd_sigma * np.random.randn()) % 360
        self.tws = (self.tws
                    + self.tws_alpha * (self.base_tws - self.tws)
                    + self.tws_sigma * np.random.randn())
        self.tws = float(np.clip(self.tws, self.tws_min, self.tws_max))
        return self.twd, self.tws


class SailboatSimulator:
    LAND_STUCK_LIMIT = 60

    def __init__(self, polar_function,
                 wind_model: WindModel | None = None,
                 land_mask: LandMask | None = None):
        self.polar      = polar_function
        self.wind_model = wind_model
        self.land_mask  = land_mask

        self.lat = self.lon = self.heading = None
        self.speed_knots = None
        self.wind_tws = self.wind_twd = None
        self.checkpoints: list = list()
        self.current_target_idx = 0
        self.time_sec = 0
        self.done = False
        self.max_steps = 0
        self._prev_distance_nm = None
        self._checkpoints_passed = 0
        self._land_stuck_counter = 0

    def reset(self, start_lat, start_lon, start_heading,
              checkpoints, wind_tws, wind_twd, max_steps=30_000):
        self.lat     = start_lat
        self.lon     = start_lon
        self.heading = float(start_heading) % 360
        self.speed_knots = 0.0
        self.checkpoints = list(checkpoints)
        self.current_target_idx = 0
        self.wind_tws = wind_tws
        self.wind_twd = wind_twd
        self.time_sec = 0
        self.done = False
        self.max_steps = max_steps
        self._land_stuck_counter = 0

        if self.wind_model is not None:
            self.wind_model.base_twd = wind_twd
            self.wind_model.base_tws = wind_tws
            self.wind_model.reset()
            self.wind_twd = self.wind_model.twd
            self.wind_tws = self.wind_model.tws

        self._prev_distance_nm = self._dist_to_target()
        self._checkpoints_passed = 0

    def _twa(self) -> float:
        twa = (self.heading - self.wind_twd) % 360
        return 360 - twa if twa > 180 else twa

    def _speed_from_polar(self, twa_deg: float) -> float:
        if twa_deg < DEAD_ZONE_DEG:
            return 0.0
        return max(0.0, self.polar(twa_deg, self.wind_tws))

    def _move(self):
        delta_nm = self.speed_knots / 3600.0
        heading_rad = math.radians(self.heading)
        self.lat += (delta_nm / 60.0) * math.cos(heading_rad)
        self.lon += (delta_nm / 60.0) / math.cos(math.radians(self.lat)) * math.sin(heading_rad)

    def _haversine(self, lat2, lon2) -> float:
        lat1_r = math.radians(self.lat)
        lat2_r = math.radians(lat2)
        dlat   = math.radians(lat2 - self.lat)
        dlon   = math.radians(lon2 - self.lon)
        a = math.sin(dlat/2)**2 + math.cos(lat1_r)*math.cos(lat2_r)*math.sin(dlon/2)**2
        return EARTH_RADIUS_NM * 2 * math.asin(min(1.0, math.sqrt(a)))

    def _dist_to_target(self) -> float:
        if self.current_target_idx >= len(self.checkpoints):
            return 0.0
        lat, lon = self.checkpoints[self.current_target_idx]
        return self._haversine(lat, lon)

    def step(self, action: float) -> tuple[np.ndarray, float, bool]:
        if self.done:
            return self.get_observations(), 0.0, True

        if self.wind_model is not None:
            self.wind_twd, self.wind_tws = self.wind_model.step()

        self.heading = (self.heading + float(action) * MAX_TURN_RATE_DEG) % 360
        twa = self._twa()
        self.speed_knots = self._speed_from_polar(twa)

        prev_lat, prev_lon = self.lat, self.lon
        self._move()
        self.time_sec += 1

        land_hit = False
        if self.land_mask is not None and self.land_mask.is_land(self.lat, self.lon):
            self.lat = prev_lat
            self.lon = prev_lon
            self.speed_knots = 0.0
            land_hit = True
            self._land_stuck_counter += 1
            if self._land_stuck_counter >= self.LAND_STUCK_LIMIT:
                self.done = True
        else:
            self._land_stuck_counter = 0

        checkpoint_hit = False
        if self.current_target_idx < len(self.checkpoints):
            if self._dist_to_target() < CHECKPOINT_RADIUS_NM:
                self._checkpoints_passed += 1
                self.current_target_idx += 1
                checkpoint_hit = True
                if self.current_target_idx >= len(self.checkpoints):
                    self.done = True

        if self.time_sec >= self.max_steps:
            self.done = True

        reward = self._compute_reward(checkpoint_hit, land_hit)
        return self.get_observations(), reward, self.done

    def _compute_reward(self, checkpoint_hit: bool, land_hit: bool) -> float:
        if land_hit:
            stuck_penalty = -5.0 * min(self._land_stuck_counter, 10)
            return -25.0 + stuck_penalty

        if self.done and self.current_target_idx >= len(self.checkpoints):
            return 2000.0 + (self.max_steps - self.time_sec) * 0.5

        if checkpoint_hit:
            return 300.0

        if self.done:
            missing = len(self.checkpoints) - self.current_target_idx
            return -200.0 * missing

        current_dist = self._dist_to_target()
        vmg = 0.0
        if self._prev_distance_nm is not None:
            vmg = (self._prev_distance_nm - current_dist) * 3600.0
        self._prev_distance_nm = current_dist

        dead_zone_penalty = -1.0 if self.speed_knots < 0.2 else 0.0
        return -1.0 + vmg * 1.0 + dead_zone_penalty

    def get_observations(self) -> np.ndarray:
        if self.current_target_idx >= len(self.checkpoints):
            return np.zeros(8, dtype=np.float32)

        tlat, tlon = self.checkpoints[self.current_target_idx]
        dx = tlon - self.lon
        dy = tlat - self.lat
        angle_to_target = math.degrees(math.atan2(dx, dy)) % 360
        rel = (angle_to_target - self.heading + 180) % 360 - 180
        twa = self._twa()

        dist_norm  = min(self._dist_to_target() / 2.0, 1.0)
        speed_norm = min(self.speed_knots / 10.0, 1.0)
        tws_norm   = float(np.clip((self.wind_tws - 4.0) / 26.0, 0.0, 1.0))

        land_proximity = min(self._land_stuck_counter / self.LAND_STUCK_LIMIT, 1.0)

        return np.array([
            math.sin(math.radians(rel)),
            math.cos(math.radians(rel)),
            math.sin(math.radians(twa)),
            math.cos(math.radians(twa)),
            dist_norm,
            speed_norm,
            tws_norm,
            land_proximity,
        ], dtype=np.float32)

    @property
    def finished(self) -> bool:
        return self.done and self.current_target_idx >= len(self.checkpoints)

    def state_dict(self) -> dict:
        return {
            "lat": self.lat, "lon": self.lon,
            "heading": self.heading,
            "speed_knots": self.speed_knots,
            "time_sec": self.time_sec,
            "checkpoints_passed": self._checkpoints_passed,
            "current_target_idx": self.current_target_idx,
            "done": self.done,
            "land_stuck": self._land_stuck_counter,
        }


if __name__ == "__main__":
    from polar_diagram import racing_polar
    import os

    mask = None
    if os.path.exists("coastline.json"):
        mask = LandMask("coastline.json")
        print("LandMask connected\n")
    else:
        print("coastline.json not found\n")

    sim = SailboatSimulator(polar_function=racing_polar, land_mask=mask)
    sim.reset(
        start_lat=43.109061, start_lon=131.865189,
        start_heading=270,
        checkpoints=[(43.109061, 131.855), (43.115, 131.860)],
        wind_tws=12.0, wind_twd=90.0, max_steps=10_000,
    )

    for i in range(300):
        obs, reward, done = sim.step(0.0)
        if i % 50 == 0:
            s = sim.state_dict()
            print(f"step={i:4d}  lat={s['lat']:.5f}  lon={s['lon']:.5f}"
                  f"  hdg={s['heading']:5.1f}°  spd={s['speed_knots']:.2f}kn"
                  f"  cp={s['checkpoints_passed']}  land={s['land_stuck']}  r={reward:+.2f}")
        if done:
            print(f"\n{'FINISHED' if sim.finished else 'TIMEOUT/STUCK'} "
                  f"in {sim.time_sec}s, cp={sim._checkpoints_passed}")
            break
        
    print("\nSimulator OK")
