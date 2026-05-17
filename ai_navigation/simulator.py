import math
import numpy as np


CHECKPOINT_RADIUS_NM = 0.027
EARTH_RADIUS_NM      = 3440.065
MAX_TURN_RATE_DEG    = 15.0
DEAD_ZONE_DEG        = 30


class SailboatSimulator:

    def __init__(self, polar_function):
        self.polar = polar_function

        self.lat = self.lon = self.heading = None
        self.speed_knots = None
        self.wind_tws = self.wind_twd = None
        self.checkpoints: list = list()
        self.current_target_idx = 0
        self.time_sec = 0
        self.done = False
        self.max_steps = 0

        self._prev_distance_nm: float | None = None
        self._checkpoints_passed = 0

    def reset(self, start_lat, start_lon, start_heading,
              checkpoints, wind_tws, wind_twd, max_steps=30_000):
        self.lat = start_lat
        self.lon = start_lon
        self.heading = float(start_heading) % 360
        self.speed_knots = 0.0
        self.checkpoints = list(checkpoints)
        self.current_target_idx = 0
        self.wind_tws = wind_tws
        self.wind_twd = wind_twd
        self.time_sec = 0
        self.done = False
        self.max_steps = max_steps

        self._prev_distance_nm = self._dist_to_target()
        self._checkpoints_passed = 0

    def _twa(self) -> float:
        twa = (self.heading - self.wind_twd) % 360
        if twa > 180:
            twa = 360 - twa
        return twa

    def _speed_from_polar(self, twa_deg: float) -> float:
        if twa_deg < DEAD_ZONE_DEG:
            return 0.0
        return max(0.0, self.polar(twa_deg, self.wind_tws))

    def _move(self):
        delta_nm = self.speed_knots / 3600.0
        heading_rad = math.radians(self.heading)

        delta_lat = (delta_nm / 60.0) * math.cos(heading_rad)
        delta_lon = (delta_nm / 60.0) / math.cos(math.radians(self.lat)) * math.sin(heading_rad)

        self.lat += delta_lat
        self.lon += delta_lon

    def _haversine(self, lat2, lon2) -> float:
        lat1_r = math.radians(self.lat)
        lat2_r = math.radians(lat2)
        dlat   = math.radians(lat2 - self.lat)
        dlon   = math.radians(lon2 - self.lon)

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        return EARTH_RADIUS_NM * 2 * math.asin(min(1.0, math.sqrt(a)))

    def _dist_to_target(self) -> float:
        if self.current_target_idx >= len(self.checkpoints):
            return 0.0
        lat, lon = self.checkpoints[self.current_target_idx]
        return self._haversine(lat, lon)

    def step(self, action: float) -> tuple[np.ndarray, float, bool]:
        if self.done:
            return self.get_observations(), 0.0, True

        turn = float(action) * MAX_TURN_RATE_DEG
        self.heading = (self.heading + turn) % 360

        twa = self._twa()
        self.speed_knots = self._speed_from_polar(twa)

        self._move()
        self.time_sec += 1

        checkpoint_hit = False
        if self.current_target_idx < len(self.checkpoints):
            dist = self._dist_to_target()
            if dist < CHECKPOINT_RADIUS_NM:
                self._checkpoints_passed += 1
                self.current_target_idx += 1
                checkpoint_hit = True
                if self.current_target_idx >= len(self.checkpoints):
                    self.done = True

        if self.time_sec >= self.max_steps:
            self.done = True

        reward = self._compute_reward(checkpoint_hit)

        return self.get_observations(), reward, self.done

    def _compute_reward(self, checkpoint_hit: bool) -> float:
        if self.done and self.current_target_idx >= len(self.checkpoints):
            time_bonus = (self.max_steps - self.time_sec) * 0.5
            return 2000.0 + time_bonus

        if checkpoint_hit:
            return 300.0

        if self.done:
            missing = len(self.checkpoints) - self.current_target_idx
            return -200.0 * missing

        current_dist = self._dist_to_target()

        vmg_knots = 0.0
        if self._prev_distance_nm is not None:
            vmg_knots = (self._prev_distance_nm - current_dist) * 3600.0
        self._prev_distance_nm = current_dist

        time_cost = -1.0

        vmg_reward = vmg_knots * 1.0

        dead_zone_penalty = -1.0 if self.speed_knots < 0.2 else 0.0

        return time_cost + vmg_reward + dead_zone_penalty

    def get_observations(self) -> np.ndarray:
        if self.current_target_idx >= len(self.checkpoints):
            return np.zeros(6, dtype=np.float32)

        tlat, tlon = self.checkpoints[self.current_target_idx]

        dx = tlon - self.lon
        dy = tlat - self.lat
        angle_to_target = math.degrees(math.atan2(dx, dy)) % 360

        rel = (angle_to_target - self.heading + 180) % 360 - 180

        twa = self._twa()

        dist = self._dist_to_target()
        dist_norm = min(dist / 2.0, 1.0)

        speed_norm = min(self.speed_knots / 10.0, 1.0)

        return np.array([
            math.sin(math.radians(rel)),
            math.cos(math.radians(rel)),
            math.sin(math.radians(twa)),
            math.cos(math.radians(twa)),
            dist_norm,
            speed_norm,
        ], dtype=np.float32)

    @property
    def finished(self) -> bool:
        return self.done and self.current_target_idx >= len(self.checkpoints)

    def state_dict(self) -> dict:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "heading": self.heading,
            "speed_knots": self.speed_knots,
            "time_sec": self.time_sec,
            "checkpoints_passed": self._checkpoints_passed,
            "current_target_idx": self.current_target_idx,
            "done": self.done,
        }


if __name__ == "__main__":
    from polar_diagram import racing_polar

    sim = SailboatSimulator(polar_function=racing_polar)
    sim.reset(
        start_lat=43.109061,
        start_lon=131.865189,
        start_heading=270,
        checkpoints=[
            (43.109061, 131.855),
            (43.115,    131.860),
        ],
        wind_tws=12.0,
        wind_twd=90.0,
        max_steps=10_000,
    )

    for step in range(200):
        obs, reward, done = sim.step(0.0)
        if step % 50 == 0:
            s = sim.state_dict()
            print(f"step={step:4d}  lat={s['lat']:.5f}  lon={s['lon']:.5f}"
                  f"  hdg={s['heading']:5.1f}°  spd={s['speed_knots']:.2f}kn"
                  f"  cp={s['checkpoints_passed']}  r={reward:+.2f}")
        if done:
            print(f"\n{'✅ FINISHED' if sim.finished else '⛔ TIMEOUT'} "
                  f"in {sim.time_sec}s, checkpoints={sim._checkpoints_passed}")
            break

    print("\nSimulator OK")
