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