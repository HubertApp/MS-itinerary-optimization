"""Collecte des observations de trafic et de meteo.

Deux sources de trafic :
  - "synthetic" : genere un profil realiste, aucune cle, marche hors ligne.
  - "tomtom"    : donnees reelles (currentTravelTime / freeFlowTravelTime).
"""

import math
import random
from datetime import datetime

from app.config import FRICTION_MAX, FRICTION_MIN


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
