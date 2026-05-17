import math


def _normalize_twa(twa_deg: float) -> float:
    twa = twa_deg % 360
    return 360 - twa if twa > 180 else twa


def _interpolate(x: float, table: dict) -> float:
    angles = sorted(table.keys())
    if x <= angles[0]:
        return table[angles[0]]
    if x >= angles[-1]:
        return table[angles[-1]]
    for i in range(len(angles) - 1):
        a, b = angles[i], angles[i + 1]
        if a <= x <= b:
            t = (x - a) / (b - a)
            return table[a] + t * (table[b] - table[a])
    return 0.0


_BASE_POLAR_12KN = {
    0:   0.0,
    30:  0.0,
    40:  3.2,
    45:  4.5,
    52:  5.4,
    60:  5.9,
    70:  6.3,
    80:  6.5,
    90:  6.6,
    100: 6.5,
    110: 6.3,
    120: 6.0,
    135: 5.6,
    150: 5.0,
    165: 4.4,
    180: 3.8,
}


def racing_polar(twa_deg: float, tws_knots: float = 12.0) -> float:
    twa = _normalize_twa(twa_deg)
    base = _interpolate(twa, _BASE_POLAR_12KN)

    wind_factor = (tws_knots / 12.0) ** 0.65
    speed = base * wind_factor

    max_speed = tws_knots * 0.75
    return min(max(speed, 0.0), max_speed)


def simple_polar(twa_deg: float, tws_knots: float = 12.0) -> float:
    twa = _normalize_twa(twa_deg)
    if twa < 30:
        return 0.0

    t = (twa - 30) / 150.0          # 0..1
    base = math.sin(t * math.pi)    # 0 → 1 → 0
    max_speed = min(tws_knots * 0.55, 8.0)
    return max_speed * base


def get_polar_fn(tws_knots: float):
    def polar(twa_deg: float, _tws: float = tws_knots) -> float:
        return racing_polar(twa_deg, tws_knots)
    return polar


def polar_to_points(tws_knots: float = 12.0, step_deg: int = 5) -> list[tuple[float, float]]:
    return list(
        (twa, racing_polar(twa, tws_knots))
        for twa in range(0, 181, step_deg)
    )


if __name__ == "__main__":
    print("TWA   |  8kn  | 12kn  | 16kn  | 20kn")
    print("------+-------+-------+-------+------")
    for twa in [0, 30, 45, 60, 90, 120, 150, 180]:
        speeds = [f"{racing_polar(twa, tws):5.2f}" for tws in [8, 12, 16, 20]]
        print(f"{twa:3d}°  | {'| '.join(speeds)}")
