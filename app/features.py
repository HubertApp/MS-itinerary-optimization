import numpy as np
import pandas as pd

VARIABLES = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "is_weekend", "is_public_holiday",
    "temperature_c", "precipitation_mm", "wind_speed_kmh",
    "tile_id",
]


def prepare(frame: pd.DataFrame) -> pd.DataFrame:
    colonne = "moment" if "moment" in frame.columns else "observed_at"
    moment = pd.to_datetime(frame[colonne], utc=True, format="mixed")

    X = pd.DataFrame(index=frame.index)
    heure = moment.dt.hour + moment.dt.minute / 60
    jour = moment.dt.dayofweek

    X["hour_sin"] = np.sin(2 * np.pi * heure / 24)
    X["hour_cos"] = np.cos(2 * np.pi * heure / 24)
    X["dow_sin"] = np.sin(2 * np.pi * jour / 7)
    X["dow_cos"] = np.cos(2 * np.pi * jour / 7)

    X["is_weekend"] = (jour >= 5).astype(int)
    X["is_public_holiday"] = frame["is_public_holiday"].astype(bool).astype(int)

    for meteo in ("temperature_c", "precipitation_mm", "wind_speed_kmh"):
        X[meteo] = pd.to_numeric(frame[meteo], errors="coerce")

    X["tile_id"] = frame["tile_id"].astype("category")
    return X[VARIABLES]