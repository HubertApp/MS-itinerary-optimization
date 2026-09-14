"""Schema GraphQL du service.

Deux publics differents, donc deux champs :

  frictionMap   destine au graph-manager et au debogage. Renvoie TOUTE la zone,
                sans filtre de position.
  disruptions   destine au fil de l'utilisateur. La position est OBLIGATOIRE :
                on ne montre que ce qui l'entoure.
"""

import math
from datetime import datetime, timezone
from typing import List, Optional

import strawberry

from app.cli import friction_map

RAYON_MINIMUM_M = 1200.0

SEUIL_RALENTI = 1.15
SEUIL_CONGESTIONNE = 1.40


def _centre_tuile(tuile: str) -> tuple[float, float]:
    """tile_id est deja `lat_arrondie:lon_arrondie` : le parser rend le centre."""
    lat, lon = tuile.split(":")
    return float(lat), float(lon)


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rayon_terre = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    return 2 * rayon_terre * math.asin(math.sqrt(a))


def _niveau(friction: float) -> str:
    if friction >= SEUIL_CONGESTIONNE:
        return "Congestionne"
    if friction >= SEUIL_RALENTI:
        return "Ralenti"
    return "Fluide"


def _heure_pleine(at: Optional[datetime]) -> datetime:
    moment = at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.replace(minute=0, second=0, microsecond=0)


@strawberry.type
class TileFriction:
    tile_id: str
    friction: float


@strawberry.type
class Disruption:
    tile_id: str
    friction: float
    niveau: str
    lat: float
    lon: float
    distance_m: float
    message: str


@strawberry.type
class Query:

    @strawberry.field(description=(
        "Carte complete de friction. Destinee au graph-manager et au debogage, "
        "PAS au fil de l'utilisateur : elle ne filtre pas sur la position."))
    def friction_map(self, at: Optional[datetime] = None) -> List[TileFriction]:
        moment = _heure_pleine(at)
        return [
            TileFriction(tile_id=tuile, friction=valeur)
            for tuile, valeur in sorted(friction_map(moment).items())
        ]

    @strawberry.field(description=(
        "Fil des perturbations AUTOUR DE L'UTILISATEUR. La position est "
        "obligatoire. Le rayon est ramene a 1200 m minimum, taille d'une tuile."))
    def disruptions(
        self,
        lat: float,
        lon: float,
        radius_m: float = 3000.0,
        at: Optional[datetime] = None,
        threshold: float = SEUIL_RALENTI,
    ) -> List[Disruption]:
        moment = _heure_pleine(at)
        rayon = max(radius_m, RAYON_MINIMUM_M)

        proches = []
        for tuile, friction in friction_map(moment).items():
            if friction < threshold:
                continue
            t_lat, t_lon = _centre_tuile(tuile)
            distance = _distance_m(lat, lon, t_lat, t_lon)
            if distance > rayon:
                continue
            niveau = _niveau(friction)
            minutes = round((friction - 1.0) * 10)
            proches.append(Disruption(
                tile_id=tuile,
                friction=round(friction, 3),
                niveau=niveau,
                lat=t_lat,
                lon=t_lon,
                distance_m=round(distance),
                message=(f"{niveau} a {round(distance)} m : comptez environ "
                         f"{minutes} min de plus sur 10 min de trajet"),
            ))

        # Le plus proche d'abord : c'est l'ordre du fil.
        return sorted(proches, key=lambda d: d.distance_m)


schema = strawberry.Schema(query=Query)