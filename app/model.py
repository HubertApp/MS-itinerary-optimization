"""Chargement et utilisation du modele entraine dans Colab.

CE FICHIER N'ENTRAINE RIEN. L'entrainement a lieu dans le notebook, qui produit
`friction.joblib`. Ici on se contente de charger ce fichier, de verifier qu'il
est compatible, et de predire.

Le calcul des variables vit dans app/features.py, qui voyage dans l'archive
d'export : le notebook importe le meme fichier, donc aucune derive possible.
"""

import joblib
import numpy as np
import pandas as pd
import sklearn

from app.config import MODEL_PATH
from app.features import prepare

_bundle = None


def charger(model_path: str = MODEL_PATH) -> dict:
    global _bundle
    if _bundle is not None:
        return _bundle

    try:
        bundle = joblib.load(model_path)
    except FileNotFoundError:
        raise RuntimeError(
            f"Aucun modele a {model_path}. Entrainez-le dans le notebook Colab, "
            f"telechargez friction.joblib et deposez-le ici."
        ) from None

    if not isinstance(bundle, dict):
        raise RuntimeError(
            f"{model_path} contient un {type(bundle).__name__} nu, pas un bundle. "
            f"Le service a besoin du vocabulaire de tuiles et de la version de "
            f"scikit-learn : utilisez la cellule d'export du notebook, pas un "
            f"joblib.dump(modele)."
        )

    manquants = {"modele", "variables", "tuiles", "sklearn"} - set(bundle)
    if manquants:
        raise RuntimeError(
            f"Bundle incomplet, champs manquants : {sorted(manquants)}. "
            f"Utilisez la cellule d'export du notebook."
        )

    if bundle["sklearn"] != sklearn.__version__:
        raise RuntimeError(
            f"Modele entraine avec scikit-learn {bundle['sklearn']}, execute avec "
            f"{sklearn.__version__}. Reentrainez dans Colab apres "
            f"`!pip install -q scikit-learn=={sklearn.__version__}`, ou alignez "
            f"requirements.txt."
        )

    _bundle = bundle
    return _bundle


def infos(model_path: str = MODEL_PATH) -> dict:
    bundle = charger(model_path)
    return {
        "tuiles_connues": len(bundle["tuiles"]),
        "variables": len(bundle["variables"]),
        "sklearn": bundle["sklearn"],
        "reference_disponible": "reference" in bundle,
    }


def predict_friction(rows: list, model_path: str = MODEL_PATH) -> np.ndarray:
    bundle = charger(model_path)
    frame = pd.DataFrame(rows)


    inconnues = sorted(set(frame["tile_id"]) - set(bundle["tuiles"]))
    if inconnues:
        raise ValueError(
            f"{len(inconnues)} tuile(s) absente(s) du modele : {inconnues[:5]}"
            f"{' ...' if len(inconnues) > 5 else ''}. "
            f"Le modele en connait {len(bundle['tuiles'])}. "
            f"Reexportez les donnees et reentrainez : config.POINTS a change."
        )

    return bundle["modele"].predict(prepare(frame))


def predire_reference(rows: list, model_path: str = MODEL_PATH) -> np.ndarray:
    """Repli sur la mediane historique, si le modele decroche un jour."""
    bundle = charger(model_path)
    reference = bundle.get("reference")
    if not reference:
        raise RuntimeError("Ce bundle ne contient pas de table de reference.")

    frame = pd.DataFrame(rows)
    moment = pd.to_datetime(
        frame["moment" if "moment" in frame.columns else "observed_at"],
        utc=True, format="mixed",
    )
    cles = (frame["tile_id"].astype(str) + "|"
            + moment.dt.dayofweek.astype(str) + "|" + moment.dt.hour.astype(str))
    return np.array([reference["table"].get(c, reference["globale"]) for c in cles])