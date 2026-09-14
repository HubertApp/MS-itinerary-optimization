"""Ligne de commande du service.

    python -m app.cli seed 8 : historique de 8 semaines (meteo reelle)
    python -m app.cli collect : une passe de collecte (a mettre en cron)
    python -m app.cli predict : carte de friction pour maintenant
    python -m app.cli predict --at 2026-08-25T18:00
    python -m app.cli event ... : declare une braderie, un match, des travaux
    python -m app.cli export : archive zip pour Colab
"""

import argparse
import sys
from datetime import datetime, timezone

from app import store
from app.calendrier import is_public_holiday
from app.collect import _weather_at, backfill, collect_now, fetch_weather
from app.config import BBOX, POINTS, tile_id
from app.model import infos, predict_friction


def _meteo_par_tuile(moment: datetime) -> dict:
    return {
        tile_id(lat, lon): _weather_at(fetch_weather(lat, lon), moment)
        for lat, lon in POINTS
    }


def friction_map(moment: datetime) -> dict:

    meteo = _meteo_par_tuile(moment)
    rows = [
        {"tile_id": tuile, "observed_at": moment.isoformat(),
         "is_public_holiday": is_public_holiday(moment), **conditions}
        for tuile, conditions in meteo.items()
    ]
    valeurs = predict_friction(rows)
    carte = {row["tile_id"]: round(float(v), 3) for row, v in zip(rows, valeurs)}

    for event in store.events_active_at(moment.isoformat()):
        for lat, lon in POINTS:
            if (event["south"] <= lat <= event["north"]
                    and event["west"] <= lon <= event["east"]):
                tuile = tile_id(lat, lon)
                carte[tuile] = round(carte.get(tuile, 1.0) * event["multiplier"], 3)

    return carte


def _moment_depuis(texte: str | None) -> datetime:
    moment = (datetime.fromisoformat(texte).replace(tzinfo=timezone.utc)
              if texte else datetime.now(timezone.utc))
    return moment.replace(minute=0, second=0, microsecond=0)


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli",
                                     description="Service de prediction de friction")
    sub = parser.add_subparsers(dest="commande", required=True)

    seed = sub.add_parser("seed", help="fabrique un historique")
    seed.add_argument("weeks", nargs="?", type=int, default=8)

    sub.add_parser("collect", help="une passe de collecte")
    sub.add_parser("infos", help="ce que le modele charge sait faire")

    predict = sub.add_parser("predict", help="carte de friction")
    predict.add_argument("--at", default=None, help="ISO 8601, defaut : maintenant")

    event = sub.add_parser("event", help="declare un evenement ponctuel")
    event.add_argument("name")
    event.add_argument("starts_at")
    event.add_argument("ends_at")
    event.add_argument("multiplier", type=float)

    export = sub.add_parser("export", help="archive zip pour Colab")
    export.add_argument("chemin", nargs="?", default=None)

    args = parser.parse_args()
    store.init()

    if args.commande == "seed":
        print(f"Historique de {args.weeks} semaines sur {len(POINTS)} points...")
        total = backfill(args.weeks)
        print(f"\n{total} observations. Base : {store.count()} documents.")

    elif args.commande == "collect":
        print(f"{collect_now()} observations enregistrees.")

    elif args.commande == "infos":
        for cle, valeur in infos().items():
            print(f"  {cle.replace('_', ' '):<22} {valeur}")

    elif args.commande == "predict":
        moment = _moment_depuis(args.at)
        print(f"Friction predite pour {moment:%Y-%m-%d %H:%M} UTC\n")
        for tuile, valeur in sorted(friction_map(moment).items()):
            barre = "#" * max(0, int((valeur - 0.9) * 30))
            print(f"  {tuile:<16} {valeur:>6.3f}  {barre}")

    elif args.commande == "event":
        store.add_event(args.name, BBOX["north"], BBOX["south"], BBOX["east"],
                        BBOX["west"], args.starts_at, args.ends_at, args.multiplier)
        print(f"Evenement '{args.name}' enregistre (x{args.multiplier}).")

    elif args.commande == "export":
        from app.export_dataset import exporter
        exporter(args.chemin)


if __name__ == "__main__":
    main()