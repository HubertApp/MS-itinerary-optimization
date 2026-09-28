"""Schema GraphQL du service.

Trois champs, pour deux publics differents :

  frictionMap      destine au graph-manager et au debogage. Renvoie TOUTE la
                   zone du modele (9 cases), sans filtre de position.
  disruptions      destine au fil de l'utilisateur. La position est OBLIGATOIRE :
                   on ne calcule que les cases de la grille globale autour d'elle.
  trafficCoverage  dit si la position est couverte (France metropolitaine),
                   pour que le front distingue "rien a signaler" de "pas de
                   prevision ici".
"""

from datetime import datetime, timezone
from typing import List, Optional

import strawberry
from strawberry.federation.schema_directives import Link

from app.cli import friction_map, prevision_autour
from app.config import en_france, tuile_modele, tuiles_autour

RAYON_MINIMUM_M = 1200.0

SEUIL_RALENTI = 1.15
SEUIL_CONGESTIONNE = 1.40


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
class TrafficCoverage:
    covered: bool = strawberry.field(description=(
        "Au moins une case du rayon est couverte par le modele."))
    tiles_total: int = strawberry.field(description="Cases de la grille dans le rayon.")
    tiles_covered: int = strawberry.field(description="Dont cases que le modele sait predire.")


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
        "Fil des perturbations AUTOUR DE L'UTILISATEUR. Autour de Dunkerque, "
        "une entree par case (~2 km) ; ailleurs en France, une seule entree pour "
        "la zone de l'utilisateur (distanceM = 0). La position est obligatoire. "
        "Liste vide aussi hors zone couverte : voir trafficCoverage."))
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
        for tuile in prevision_autour(moment, lat, lon, rayon)["tuiles"]:
            friction = tuile["friction"]
            if friction < threshold:
                continue
            niveau = _niveau(friction)
            distance = round(tuile["distance_m"])
            minutes = round((friction - 1.0) * 10)
            proches.append(Disruption(
                tile_id=tuile["tile_id"],
                friction=round(friction, 3),
                niveau=niveau,
                lat=tuile["lat"],
                lon=tuile["lon"],
                distance_m=distance,
                message=(f"{niveau} a {distance} m : comptez environ "
                         f"{minutes} min de plus sur 10 min de trajet"),
            ))

        # Le plus proche d'abord : c'est l'ordre du fil.
        return sorted(proches, key=lambda d: d.distance_m)

    @strawberry.field(description=(
        "Couverture autour d'une position : toute la France metropolitaine. "
        "Ne charge pas le modele et n'appelle pas la meteo : peu couteux."))
    def traffic_coverage(
        self,
        lat: float,
        lon: float,
        radius_m: float = 3000.0,
    ) -> TrafficCoverage:
        autour = tuiles_autour(lat, lon, max(radius_m, RAYON_MINIMUM_M))
        couvertes = sum(1 for t in autour if tuile_modele(t["lat"], t["lon"]))
        if not couvertes and en_france(lat, lon):
            couvertes = 1  # une prevision "quartier moyen" pour la zone
        return TrafficCoverage(
            covered=couvertes > 0,
            tiles_total=len(autour),
            tiles_covered=couvertes,
        )

schema = strawberry.federation.Schema(
    query=Query,
    schema_directives=[
        Link(url="https://specs.apollo.dev/federation/v2.11", import_=["@key"]),
    ],
)
