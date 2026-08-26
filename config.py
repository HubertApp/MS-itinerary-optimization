import os

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

DB_PATH = os.getenv("DB_PATH", "mongodb")
MODEL_PATH = os.getenv("MODEL_PATH", "friction.joblib")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://user:password@localhost:5672/")

FRICTION_MIN, FRICTION_MAX = 0.5, 3.0


def tile_id(lat: float, lon: float) -> str:
    return f"{round(lat, 2)}:{round(lon, 2)}"