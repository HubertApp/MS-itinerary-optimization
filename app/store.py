"""Stockage MongoDB des observations de trafic et des evenements.

Deux collections :
  - "observations" : denormalisee, la meteo vit dans le document plutot que
    dans une collection a part. Pas de $lookup a l'entrainement.
  - "events"       : fenetres spatio-temporelles (travaux, manifestations)
    qui multiplient la friction sur une zone.

pymongo et non motor : le POC est synchrone de bout en bout, et rendre le
collecteur asynchrone n'apporterait rien a ce volume.
"""

from datetime import datetime, timezone
from typing import Iterable

from pymongo import ASCENDING, MongoClient, UpdateOne

from app.config import MONGODB_DB, MONGODB_URL

OBSERVATIONS = "observations"
EVENTS = "events"

_client: MongoClient | None = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URL, tz_aware=True)
    return _client[MONGODB_DB]


def _parse(moment_iso: str) -> datetime:
    """Mongo stocke de vraies dates, pas des chaines : les comparaisons
    temporelles fonctionnent alors nativement."""
    parsed = datetime.fromisoformat(moment_iso)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def init() -> None:
    """Cree les index. Idempotent : rejouable a chaque demarrage."""
    _db()[OBSERVATIONS].create_index(
        [("tile_id", ASCENDING), ("observed_at", ASCENDING)],
        unique=True,
        name="tile_moment",
    )
    _db()[EVENTS].create_index(
        [("starts_at", ASCENDING), ("ends_at", ASCENDING)], name="fenetre"
    )


def save_observations(rows: Iterable[dict]) -> int:
    """Upsert : rejouer une collecte ne cree pas de doublon."""
    rows = list(rows)
    if not rows:
        return 0

    operations = [
        UpdateOne(
            {"tile_id": row["tile_id"], "observed_at": _parse(row["observed_at"])},
            {"$set": {**row, "observed_at": _parse(row["observed_at"])}},
            upsert=True,
        )
        for row in rows
    ]
    _db()[OBSERVATIONS].bulk_write(operations, ordered=False)
    return len(rows)


def load_observations() -> list[dict]:
    """Renvoie observed_at en chaine ISO : le modele attend une chaine, donc
    toute la conversion reste enfermee ici et les autres modules ignorent que
    Mongo manipule des datetime."""
    cursor = _db()[OBSERVATIONS].find({}, {"_id": 0}).sort("observed_at", ASCENDING)
    return [
        {**document, "observed_at": document["observed_at"].isoformat()}
        for document in cursor
    ]


def count() -> int:
    return _db()[OBSERVATIONS].count_documents({})


def add_event(
    name: str,
    north: float,
    south: float,
    east: float,
    west: float,
    starts_at: str,
    ends_at: str,
    multiplier: float,
) -> None:
    _db()[EVENTS].insert_one(
        {
            "name": name,
            "north": north,
            "south": south,
            "east": east,
            "west": west,
            "starts_at": _parse(starts_at),
            "ends_at": _parse(ends_at),
            "multiplier": multiplier,
        }
    )


def events_active_at(moment_iso: str) -> list[dict]:
    moment = _parse(moment_iso)
    cursor = _db()[EVENTS].find(
        {"starts_at": {"$lte": moment}, "ends_at": {"$gte": moment}}, {"_id": 0}
    )
    return list(cursor)
