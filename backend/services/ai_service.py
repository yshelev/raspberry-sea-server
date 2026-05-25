import json
import math
import os
import random
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def _find_ai_nav_dir() -> Path:
    candidates = [
        Path("/app/ai_navigation"),
        Path(__file__).parent.parent.parent / "ai_navigation",
        Path(__file__).parent.parent / "ai_navigation",
        Path.cwd() / "ai_navigation",
        Path.cwd().parent / "ai_navigation",
    ]
    for c in candidates:
        if (c / "best_network.json").exists():
            logger.info(f"AI: found ai_navigation folder: {c}")
            return c
    logger.error(f"AI: best_network.json not found: {[str(c) for c in candidates]}")
    return candidates[0]

AI_NAV_DIR = _find_ai_nav_dir()


class _NeuralNetwork:

    def __init__(self, input_size, hidden_size, output_size):
        self.input_size  = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        w1 = hidden_size * input_size
        b1 = hidden_size
        w2 = output_size * hidden_size
        b2 = output_size
        self._n = w1 + b1 + w2 + b2
        self._sizes = [w1, b1, w2, b2]
        self.params = np.zeros(self._n)

    def _split(self):
        idx = np.cumsum([0] + self._sizes)
        W1 = self.params[idx[0]:idx[1]].reshape(self.hidden_size, self.input_size)
        b1 = self.params[idx[1]:idx[2]]
        W2 = self.params[idx[2]:idx[3]].reshape(self.output_size, self.hidden_size)
        b2 = self.params[idx[3]:idx[4]]
        return W1, b1, W2, b2

    def predict(self, obs):
        W1, b1, W2, b2 = self._split()
        h = np.tanh(W1 @ np.array(obs, dtype=np.float32) + b1)
        return float(np.tanh(W2 @ h + b2)[0])

    @classmethod
    def load(cls, path):
        with open(path) as f:
            d = json.load(f)
        net = cls(d["input_size"], d["hidden_size"], d["output_size"])
        net.params = np.array(d["params"])
        return net


class _LandMask:

    def __init__(self, meta_path):
        from PIL import Image
        with open(meta_path) as f:
            meta = json.load(f)
        mask_path = meta["mask_file"]
        if not os.path.exists(mask_path):
            base = os.path.dirname(os.path.abspath(meta_path))
            mask_path = os.path.join(base, os.path.basename(mask_path))
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

    def is_land(self, lat, lon):
        if not (self.bbox["min_lat"] <= lat <= self.bbox["max_lat"] and
                self.bbox["min_lon"] <= lon <= self.bbox["max_lon"]):
            return False
        col = int((lon - self._nw_lon) * self._lon_scale)
        row = int((self._nw_lat - lat) * self._lat_scale)
        col = max(0, min(col, self._w - 1))
        row = max(0, min(row, self._h - 1))
        return self._mask[row, col] < 128


CHECKPOINT_RADIUS_NM = 0.027

EARTH_RADIUS_NM   = 3440.065
MAX_TURN_RATE_DEG = 15.0
DEAD_ZONE_DEG     = 30
TRAJECTORY_STEP   = 30

DEFAULT_MAX_STEPS = 120_000

LAND_STUCK_LIMIT = 600


def _haversine(lat1, lon1, lat2, lon2):
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(lat1r)*math.cos(lat2r)*math.sin(dlon/2)**2
    return EARTH_RADIUS_NM * 2 * math.asin(min(1.0, math.sqrt(a)))


def _run_simulation(net, checkpoints, start_lat, start_lon,
                    wind_twd, wind_tws, land_mask=None,
                    max_steps=DEFAULT_MAX_STEPS, initial_heading=0.0):
    lat = start_lat
    lon = start_lon
    heading = initial_heading
    speed = 0.0
    current_idx = 0
    time_sec = 0
    land_stuck = 0
    escape_attempts = 0

    trajectory = [[lat, lon]]
    checkpoints_passed = 0

    def twa():
        t = (heading - wind_twd) % 360
        return 360 - t if t > 180 else t

    def polar(twa_deg, tws):
        if twa_deg < DEAD_ZONE_DEG:
            return 0.0
        table = {0:0,30:0,40:3.2,45:4.5,52:5.4,60:5.9,70:6.3,
                 80:6.5,90:6.6,100:6.5,110:6.3,120:6.0,
                 135:5.6,150:5.0,165:4.4,180:3.8}
        angles = sorted(table.keys())
        t = min(max(twa_deg, 0), 180)
        for i in range(len(angles)-1):
            a, b = angles[i], angles[i+1]
            if a <= t <= b:
                frac = (t-a)/(b-a)
                base = table[a] + frac*(table[b]-table[a])
                factor = (tws/12.0)**0.65
                return min(max(base*factor, 0), tws*0.75)
        return 0.0

    def dist_to(idx):
        if idx >= len(checkpoints):
            return 0.0
        return _haversine(lat, lon, checkpoints[idx][0], checkpoints[idx][1])

    prev_dist = dist_to(current_idx)

    for step in range(max_steps):
        if current_idx >= len(checkpoints):
            obs = [0.0] * 8
        else:
            tlat, tlon = checkpoints[current_idx]
            dx = tlon - lon
            dy = tlat - lat
            angle_to = math.degrees(math.atan2(dx, dy)) % 360
            rel = (angle_to - heading + 180) % 360 - 180
            tw = twa()
            cur_dist = _haversine(lat, lon, tlat, tlon)
            obs = [
                math.sin(math.radians(rel)),
                math.cos(math.radians(rel)),
                math.sin(math.radians(tw)),
                math.cos(math.radians(tw)),
                min(cur_dist / 2.0, 1.0),
                min(speed / 10.0, 1.0),
                float(np.clip((wind_tws - 4.0) / 26.0, 0.0, 1.0)),
                min(land_stuck / LAND_STUCK_LIMIT, 1.0),
            ]

        action = net.predict(obs)
        heading = (heading + action * MAX_TURN_RATE_DEG) % 360
        tw = twa()
        speed = polar(tw, wind_tws)

        delta_nm = speed / 3600.0
        heading_rad = math.radians(heading)
        new_lat = lat + (delta_nm / 60.0) * math.cos(heading_rad)
        new_lon = lon + (delta_nm / 60.0) / math.cos(math.radians(lat)) * math.sin(heading_rad)

        if land_mask and land_mask.is_land(new_lat, new_lon):
            land_stuck += 1
            speed = 0.0

            if land_stuck % 10 == 0:
                escape_attempts += 1
                base_turn = (escape_attempts * 40) % 360
                jitter = random.uniform(-20, 20)
                heading = (heading + base_turn + jitter) % 360

            if land_stuck >= LAND_STUCK_LIMIT:
                logger.info(
                    f"AI: застряли в земле (cp={current_idx}/{len(checkpoints)}), прерываем на шаге {step}"
                )
                break
        else:
            lat, lon = new_lat, new_lon
            if land_stuck > 0:
                land_stuck = 0
                escape_attempts = 0

        time_sec += 1

        if step % TRAJECTORY_STEP == 0:
            trajectory.append([round(lat, 6), round(lon, 6)])

        if current_idx < len(checkpoints):
            d = _haversine(lat, lon, checkpoints[current_idx][0], checkpoints[current_idx][1])
            if d < CHECKPOINT_RADIUS_NM:
                checkpoints_passed += 1
                current_idx += 1
                trajectory.append([round(lat, 6), round(lon, 6)])
                prev_dist = dist_to(current_idx)
                if current_idx >= len(checkpoints):
                    break

    return trajectory, heading, time_sec, checkpoints_passed


def _smooth_trajectory(trajectory: list) -> list:
    if len(trajectory) <= 2:
        return trajectory

    result = [trajectory[0]]

    for i in range(1, len(trajectory) - 1):
        p0 = result[-1]
        p1 = trajectory[i]
        p2 = trajectory[i + 1]

        dx1 = p1[1] - p0[1]
        dy1 = p1[0] - p0[0]
        b1 = math.degrees(math.atan2(dx1, dy1)) % 360

        dx2 = p2[1] - p1[1]
        dy2 = p2[0] - p1[0]
        b2 = math.degrees(math.atan2(dx2, dy2)) % 360

        angle_diff = abs((b2 - b1 + 180) % 360 - 180)
        dist = _haversine(p0[0], p0[1], p1[0], p1[1])

        if angle_diff > 3.0 or dist > 0.05:
            result.append(p1)

    result.append(trajectory[-1])
    return result


_net = None
_land_mask = None
_loaded = False


def _ensure_loaded():
    global _net, _land_mask, _loaded
    if _loaded:
        return

    net_path  = AI_NAV_DIR / "best_network.json"
    mask_path = AI_NAV_DIR / "coastline.json"

    if net_path.exists():
        try:
            _net = _NeuralNetwork.load(str(net_path))
            logger.info(f"AI: нейросеть загружена из {net_path}")
        except Exception as e:
            logger.error(f"AI: ошибка загрузки сети: {e}")

    if mask_path.exists():
        try:
            _land_mask = _LandMask(str(mask_path))
            logger.info("AI: маска суши загружена")
        except Exception as e:
            logger.warning(f"AI: маска суши не загружена: {e}")

    _loaded = True


async def compute_ai_route(
    checkpoints: list[dict],
    start_lat: float,
    start_lon: float,
    wind_twd: float,
    wind_tws: float,
) -> dict:
    _ensure_loaded()

    if _net is None:
        return {
            "error": "Нейросеть не загружена. Убедись что best_network.json существует.",
            "trajectory": [],
            "recommended_heading": None,
            "estimated_time_sec": None,
            "checkpoints_reachable": 0,
        }

    if not checkpoints:
        return {
            "error": "Маршрут пуст — добавь точки на карте.",
            "trajectory": [],
            "recommended_heading": None,
            "estimated_time_sec": None,
            "checkpoints_reachable": 0,
        }

    cp_list = [(c["lat"], c["lon"]) for c in checkpoints]

    first_cp_lat, first_cp_lon = cp_list[0]
    dist_to_first = _haversine(start_lat, start_lon, first_cp_lat, first_cp_lon)
    if dist_to_first < 1.0:
        sim_start_lat, sim_start_lon = start_lat, start_lon
    else:
        sim_start_lat, sim_start_lon = first_cp_lat, first_cp_lon
        logger.info(f"AI: GPS далеко от старта ({dist_to_first:.2f} NM), стартуем из первой точки")

    best_result = None
    best_score = float("-inf")
    N_RUNS = 8
    initial_headings = [i * (360.0 / N_RUNS) for i in range(N_RUNS)]

    for run_i, init_hdg in enumerate(initial_headings):
        traj, final_hdg, t, cp_passed = _run_simulation(
            _net, cp_list, sim_start_lat, sim_start_lon,
            wind_twd, wind_tws, _land_mask,
            max_steps=DEFAULT_MAX_STEPS,
            initial_heading=init_hdg,
        )
        score = cp_passed * 10_000_000 - t
        logger.info(f"AI run {run_i}: hdg0={init_hdg:.0f}° cp={cp_passed}/{len(cp_list)} t={t}s score={score:.0f}")
        if score > best_score:
            best_score = score
            best_result = (traj, final_hdg, t, cp_passed)

    trajectory, final_heading, time_sec, cp_passed = best_result
    trajectory = _smooth_trajectory(trajectory)

    recommended_heading = None
    if len(trajectory) >= 2:
        p1, p2 = trajectory[0], trajectory[1]
        dx = p2[1] - p1[1]
        dy = p2[0] - p1[0]
        recommended_heading = round((math.degrees(math.atan2(dx, dy)) + 360) % 360, 1)

    return {
        "trajectory": trajectory,
        "recommended_heading": recommended_heading,
        "estimated_time_sec": time_sec,
        "estimated_time_min": round(time_sec / 60, 1),
        "checkpoints_reachable": cp_passed,
        "total_checkpoints": len(checkpoints),
        "wind_twd": wind_twd,
        "wind_tws": wind_tws,
    }