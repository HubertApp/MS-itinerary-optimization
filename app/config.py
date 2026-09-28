import math
import os

from dotenv import load_dotenv

load_dotenv()


BBOX = {"north": 51.06, "south": 50.98, "east": 2.46, "west": 2.28}


def _grille(n: int = 3):
    points = []
    for i in range(n):
        for j in range(n):
            lat = BBOX["south"] + (BBOX["north"] - BBOX["south"]) * (i + 0.5) / n
            lon = BBOX["west"] + (BBOX["east"] - BBOX["west"]) * (j + 0.5) / n
            points.append((round(lat, 4), round(lon, 4)))
    return points


POINTS = _grille(3)

TRAFFIC_SOURCE = os.getenv("TRAFFIC_SOURCE", "synthetic")
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "optimization_db")
MODEL_PATH = os.getenv("MODEL_PATH", "friction.joblib")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://user:password@localhost:5672/")

FRICTION_MIN, FRICTION_MAX = 0.5, 3.0


def tile_id(lat: float, lon: float) -> str:
    return f"{round(lat, 2)}:{round(lon, 2)}"


PAS_LAT = 0.02
PAS_LON = 0.03


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rayon_terre = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    return 2 * rayon_terre * math.asin(math.sqrt(a))


def tuiles_autour(lat: float, lon: float, rayon_m: float) -> list[dict]:
    d_lat = rayon_m / 111_320
    d_lon = rayon_m / (111_320 * math.cos(math.radians(lat)))

    i_min = math.floor((lat - d_lat) / PAS_LAT)
    i_max = math.floor((lat + d_lat) / PAS_LAT)
    j_min = math.floor((lon - d_lon) / PAS_LON)
    j_max = math.floor((lon + d_lon) / PAS_LON)

    tuiles = []
    for i in range(i_min, i_max + 1):
        for j in range(j_min, j_max + 1):
            c_lat = round((i + 0.5) * PAS_LAT, 4)
            c_lon = round((j + 0.5) * PAS_LON, 4)
            distance = distance_m(lat, lon, c_lat, c_lon)
            if distance <= rayon_m:
                tuiles.append({
                    "tile_id": f"{i * PAS_LAT:.2f}:{j * PAS_LON:.2f}",
                    "lat": c_lat,
                    "lon": c_lon,
                    "distance_m": distance,
                })
    return tuiles


def tuile_modele(lat: float, lon: float) -> str | None:
    if not (BBOX["south"] <= lat <= BBOX["north"]
            and BBOX["west"] <= lon <= BBOX["east"]):
        return None
    p_lat, p_lon = min(POINTS, key=lambda p: distance_m(lat, lon, p[0], p[1]))
    return tile_id(p_lat, p_lon)

FRANCE_BBOX = {"north": 51.1, "south": 41.3, "east": 9.6, "west": -5.2}


def en_france(lat: float, lon: float) -> bool:
    return (FRANCE_BBOX["south"] <= lat <= FRANCE_BBOX["north"]
            and FRANCE_BBOX["west"] <= lon <= FRANCE_BBOX["east"])


def case_de(lat: float, lon: float) -> dict:
    i, j = math.floor(lat / PAS_LAT), math.floor(lon / PAS_LON)
    return {
        "tile_id": f"{i * PAS_LAT:.2f}:{j * PAS_LON:.2f}",
        "lat": round((i + 0.5) * PAS_LAT, 4),
        "lon": round((j + 0.5) * PAS_LON, 4),
    }
