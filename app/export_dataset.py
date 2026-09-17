import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import sklearn

from app import store


def exporter(chemin: str | None = None) -> Path:
    store.init()
    rows = store.load_observations()

    if not rows:
        print("Aucune observation. Lancez d'abord : python -m app.cli seed 8")
        sys.exit(1)

    frame = pd.DataFrame(rows)
    moments = pd.to_datetime(frame["observed_at"], utc=True, format="mixed")

    archive = Path(chemin or f"observations_{datetime.now():%Y%m%d}.zip")

    manifeste = {
        "exporte_le": datetime.now(timezone.utc).isoformat(),
        "lignes": len(frame),
        "colonnes": list(frame.columns),
        "tuiles": sorted(frame["tile_id"].unique()),
        "periode": {
            "debut": moments.min().isoformat(),
            "fin": moments.max().isoformat(),
        },
        "sources": (frame["source"].value_counts().to_dict()
                    if "source" in frame else {}),
        "sklearn_cible": sklearn.__version__,
    }

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("observations.csv", frame.to_csv(index=False))
        zf.writestr("manifest.json", json.dumps(manifeste, indent=2, ensure_ascii=False))

    print(f"{archive}  ({archive.stat().st_size / 1024:.0f} Ko)")
    print(f"lignes  : {manifeste['lignes']}")
    print(f"tuiles  : {len(manifeste['tuiles'])}")
    print(f"periode : du {moments.min():%Y-%m-%d} au {moments.max():%Y-%m-%d}")
    print(f"sources : {manifeste['sources'] or 'non renseignees'}")
    print(f"sklearn : {manifeste['sklearn_cible']}")
    return archive


if __name__ == "__main__":
    exporter(sys.argv[1] if len(sys.argv) > 1 else None)