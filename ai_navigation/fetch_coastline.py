import json
import math
import os
import time
import numpy as np
import requests
from PIL import Image
import io

BBOX = {
    "min_lat": 42.50,
    "min_lon": 131.35,
    "max_lat": 43.30,
    "max_lon": 133.00,
}
ZOOM = 11

TILE_SERVERS = [
    "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
]

OUTPUT_MASK  = "land_mask.png"
OUTPUT_META  = "coastline.json"

HEADERS = {"User-Agent": "SailingAI/1.0 (academic project)"}


def deg2tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    lat_r = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y


def tile2deg(x: int, y: int, zoom: int) -> tuple[float, float]:
    n = 2 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_r = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_r)
    return lat, lon


def fetch_tile(x: int, y: int, zoom: int, server_url: str) -> Image.Image | None:
    url = server_url.replace("{z}", str(zoom)).replace("{x}", str(x)).replace("{y}", str(y))
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
        else:
            print(f"  HTTP {resp.status_code} для {url}")
    except Exception as e:
        print(f"  Error: {e}")
    return None


def download_tiles(bbox: dict, zoom: int) -> tuple[Image.Image, dict]:
    x0, y0 = deg2tile(bbox["max_lat"], bbox["min_lon"], zoom)  # NW
    x1, y1 = deg2tile(bbox["min_lat"], bbox["max_lon"], zoom)  # SE

    nx = x1 - x0 + 1
    ny = y1 - y0 + 1
    tile_px = 256

    print(f"Tiles zoom={zoom}: x=[{x0}..{x1}] y=[{y0}..{y1}] ({nx}×{ny} = {nx*ny} tiles)")

    canvas = Image.new("RGB", (nx * tile_px, ny * tile_px), (255, 255, 255))

    server = TILE_SERVERS[0]

    for yi, ty in enumerate(range(y0, y1 + 1)):
        for xi, tx in enumerate(range(x0, x1 + 1)):
            print(f"  Downloading tile ({tx}, {ty})...", end=" ")
            tile = fetch_tile(tx, ty, zoom, server)
            if tile:
                canvas.paste(tile, (xi * tile_px, yi * tile_px))
                print("OK")
            else:
                print("FAIL")
            time.sleep(0.1)

    nw_lat, nw_lon = tile2deg(x0,     y0,     zoom)
    se_lat, se_lon = tile2deg(x1 + 1, y1 + 1, zoom)

    geo_meta = {
        "nw_lat": nw_lat, "nw_lon": nw_lon,
        "se_lat": se_lat, "se_lon": se_lon,
        "width_px":  nx * tile_px,
        "height_px": ny * tile_px,
        "zoom": zoom,
    }

    print(f"Image: {canvas.size[0]}×{canvas.size[1]} px")
    print(f"Georeferencing: ({nw_lat:.4f},{nw_lon:.4f}) → ({se_lat:.4f},{se_lon:.4f})")

    return canvas, geo_meta


def build_water_mask(image: Image.Image, server_url: str) -> np.ndarray:
    arr = np.array(image, dtype=np.float32)
    R, G, B = arr[:,:,0], arr[:,:,1], arr[:,:,2]
    gray = (R + G + B) / 3

    is_water = (gray < 225) & (B >= R - 2)

    water_pct = is_water.mean() * 100

    return is_water.astype(np.uint8)


def save_mask(mask: np.ndarray, geo_meta: dict, bbox: dict):
    mask_img = Image.fromarray(mask * 255)
    mask_img.save(OUTPUT_MASK)

    meta = {
        "type": "raster",
        "mask_file": OUTPUT_MASK,
        "bbox": bbox,
        "geo": geo_meta,
        "water_value": 255,
        "land_value": 0,
    }
    with open(OUTPUT_META, "w") as f:
        json.dump(meta, f, indent=2)
        print("Mask created")


if __name__ == "__main__":
    print("=" * 60)
    print("  LAND MASK BUILDER — Amur Bay, Vladivostok")
    print("=" * 60)
    print(f"Tile server: {TILE_SERVERS[0]}")
    print()

    image, geo_meta = download_tiles(BBOX, ZOOM)

    image.save("map_raw.png")
    print("Map saved: map_raw.png")

    mask = build_water_mask(image, TILE_SERVERS[0])
    save_mask(mask, geo_meta, BBOX)
