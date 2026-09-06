"""Collecte des observations de trafic et de meteo.

Deux sources de trafic :
  - "synthetic" : genere un profil realiste, aucune cle, marche hors ligne.
  - "tomtom"    : donnees reelles (currentTravelTime / freeFlowTravelTime).
"""

import json
import math
import random
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from app.calendrier import is_public_holiday
from app.config import (
    FRICTION_MAX,
    FRICTION_MIN,
    POINTS,
    TOMTOM_API_KEY,
    TRAFFIC_SOURCE,
    tile_id,
)
from app.store import save_observations


def _tile_busyness(tile: str) -> float:
    """Certaines tuiles sont structurellement plus chargees que d'autres.
    Deterministe, pour que l'historique reste coherent d'un appel a l'autre."""
    return 0.75 + random.Random(tile).random() * 0.6


def synthetic_friction(moment: datetime, tile: str, precipitation_mm: float) -> float:
    """Profil de congestion plausible, que le modele doit pouvoir retrouver."""
    hour = moment.hour + moment.minute / 60
    weekend = moment.weekday() >= 5

    morning = 0.45 * math.exp(-((hour - 8.0) ** 2) / (2 * 1.0**2))
    evening = 0.55 * math.exp(-((hour - 17.5) ** 2) / (2 * 1.2**2))
    night = -0.10 if hour < 6 else 0.0

    peaks = (morning + evening) * (0.25 if weekend else 1.0)
    rain = 0.12 * min(precipitation_mm, 3.0) / 3.0
    noise = random.Random(f"{tile}{moment:%Y%m%d%H}").gauss(0, 0.05)

    value = (1.0 + peaks + night + rain) * _tile_busyness(tile) ** 0.5 + noise
    return round(max(FRICTION_MIN, min(FRICTION_MAX, value)), 3)


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
HOURLY = "temperature_2m,precipitation,wind_speed_10m"


def _get_json(url: str, params: dict) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full, timeout=20) as response:
        return json.load(response)


def fetch_weather(lat, lon, start_date=None, end_date=None) -> dict:
    """Retourne {datetime_iso: {temperature_c, precipitation_mm, wind_speed_kmh}}.

    Avec start_date/end_date on interroge l'archive des PREVISIONS passees, pas
    la reanalyse : en production le modele sera servi avec une prevision
    imparfaite, il doit donc etre entraine sur des previsions imparfaites.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": HOURLY,
        "timezone": "UTC",
    }
    if start_date and end_date:
        url = ARCHIVE_URL
        params["start_date"] = start_date
        params["end_date"] = end_date
    else:
        url = FORECAST_URL
        params["forecast_days"] = 2

    try:
        payload = _get_json(url, params)
    except Exception as error:  # noqa: BLE001
        print(f"  meteo indisponible ({error}) -> repli synthetique")
        return {}

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    return {
        moment: {
            "temperature_c": hourly["temperature_2m"][index],
            "precipitation_mm": hourly["precipitation"][index],
            "wind_speed_kmh": hourly["wind_speed_10m"][index],
        }
        for index, moment in enumerate(times)
    }


def _fake_weather(moment: datetime) -> dict:
    """Meteo de repli, deterministe : saisonnalite grossiere et averses.

    Rend le POC utilisable hors ligne ou derriere un proxy qui bloque les
    domaines externes.
    """
    day_of_year = moment.timetuple().tm_yday
    seasonal = 11 + 9 * math.sin(2 * math.pi * (day_of_year - 100) / 365)
    daily = 4 * math.sin(2 * math.pi * (moment.hour - 9) / 24)
    generator = random.Random(f"{moment:%Y%m%d%H}")
    rain = round(generator.random() ** 4 * 5, 2)  # souvent 0, parfois averse
    return {
        "temperature_c": round(seasonal + daily + generator.uniform(-2, 2), 1),
        "precipitation_mm": rain,
        "wind_speed_kmh": round(8 + generator.random() * 25, 1),
    }


WEATHER_FIELDS = ("temperature_c", "precipitation_mm", "wind_speed_kmh")


def _weather_at(weather_by_hour: dict, moment: datetime) -> dict:
    """Meteo de l'heure, ou repli complet.

    Open-Meteo peut renvoyer une cle horaire presente avec des valeurs nulles
    en bord d'intervalle. Sans ce garde-fou on insere des None, et le modele
    se degrade sans qu'aucune erreur ne le signale. On remplace la meteo
    entiere plutot que le champ manquant, pour garder la ligne coherente.
    """
    weather = weather_by_hour.get(moment.strftime("%Y-%m-%dT%H:00"))
    if not weather or any(weather.get(field) is None for field in WEATHER_FIELDS):
        return _fake_weather(moment)
    return weather


def _observation_rows(tile, weather_by_hour, start, end, source):
    """Genere une observation par heure sur [start, end[.

    Separe de backfill pour que la construction des lignes soit verifiable
    sans base de donnees.
    """
    moment = start
    while moment < end:
        weather = _weather_at(weather_by_hour, moment)
        yield {
            "tile_id": tile,
            "observed_at": moment.isoformat(),
            "friction": synthetic_friction(moment, tile, weather["precipitation_mm"]),
            "is_public_holiday": is_public_holiday(moment),
            "source": source,
            **weather,
        }
        moment += timedelta(hours=1)


def backfill(weeks: int = 8) -> int:
    """Fabrique un historique d'un coup, pour ne pas attendre un mois avant de
    pouvoir entrainer quoi que ce soit.

    La meteo est REELLE (archive Open-Meteo), le trafic est synthetique.
    """
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(weeks=weeks)
    total = 0

    for lat, lon in POINTS:
        tile = tile_id(lat, lon)
        weather_by_hour = fetch_weather(
            lat,
            lon,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
        )
        rows = list(_observation_rows(tile, weather_by_hour, start, end, "backfill"))
        total += save_observations(rows)
        print(f"  {tile} : {len(rows)} lignes")

    return total


TOMTOM_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"


def tomtom_friction(lat: float, lon: float) -> float | None:
    """currentTravelTime / freeFlowTravelTime : deja dans la bonne unite.

    Retourne None des que la donnee est indisponible, pour laisser l'appelant
    basculer sur le synthetique.
    """
    if not TOMTOM_API_KEY:
        return None
    try:
        payload = _get_json(TOMTOM_URL, {"key": TOMTOM_API_KEY, "point": f"{lat},{lon}"})
        data = payload["flowSegmentData"]
        if data.get("roadClosure"):
            return FRICTION_MAX
        ratio = data["currentTravelTime"] / max(data["freeFlowTravelTime"], 1)
        return round(max(FRICTION_MIN, min(FRICTION_MAX, ratio)), 3)
    except Exception as error:  # noqa: BLE001
        print(f"  tomtom indisponible ({error})")
        return None


def collect_now() -> int:
    """Une passe de collecte, a lancer toutes les 15 minutes en cron.

    Repli en cascade TomTom -> synthetique : une cle absente, un quota depasse
    ou une panne reseau n'interrompt jamais le remplissage de la base.
    """
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    rows = []

    for lat, lon in POINTS:
        tile = tile_id(lat, lon)
        weather = _weather_at(fetch_weather(lat, lon), now)

        friction = tomtom_friction(lat, lon) if TRAFFIC_SOURCE == "tomtom" else None
        if friction is None:
            friction = synthetic_friction(now, tile, weather["precipitation_mm"])

        rows.append({
            "tile_id": tile,
            "observed_at": now.isoformat(),
            "friction": friction,
            "is_public_holiday": is_public_holiday(now),
            "source": TRAFFIC_SOURCE,
            **weather,
        })

    return save_observations(rows)
