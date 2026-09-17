"""Annotation calendaire des observations.

Un jour ferie ressemble a un dimanche du point de vue du trafic : pas de
pointe domicile-travail. Sans cette variable, le modele ne voit qu'un mardi
anormalement calme et met le residu dans le bruit.

Ne couvre que les jours feries. Les vacances scolaires demandent une autre
source (le paquet holidays ne les fournit pas) et restent a faire.
"""

from datetime import date, datetime
from functools import lru_cache

import holidays

COUNTRY = "FR"


@lru_cache(maxsize=None)
def _calendar(year: int) -> holidays.HolidayBase:
    """Le calendrier d'une annee est reconstruit a chaque appel par la
    bibliotheque : on le met en cache, le backfill interroge 60 000 fois."""
    return holidays.country_holidays(COUNTRY, years=year)


def _as_date(moment: date | datetime | str) -> date:
    if isinstance(moment, str):
        moment = datetime.fromisoformat(moment)
    return moment.date() if isinstance(moment, datetime) else moment


def is_public_holiday(moment: date | datetime | str) -> bool:
    """Accepte une date, un datetime ou une chaine ISO : les observations
    relues depuis Mongo portent observed_at sous forme de chaine."""
    day = _as_date(moment)
    return day in _calendar(day.year)


def holiday_name(moment: date | datetime | str) -> str | None:
    """Nom du jour ferie, ou None. Utile pour inspecter les donnees."""
    day = _as_date(moment)
    return _calendar(day.year).get(day)
