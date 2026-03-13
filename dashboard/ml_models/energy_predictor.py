# pyright: reportMissingImports=false, reportMissingModuleSource=false
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ..models import Building
from .data_loader import (
    BASELINE_CAMPUS_POPULATION,
    BASELINE_YEAR,
    EXAM_FEATURE_MONTHS,
    PEAK_SUMMER_MONTHS,
    POPULATION_GROWTH,
    STUDY_LEAVE_FEATURE_MONTHS,
    load_energy_consumption_dataframe,
)

MODEL_PATH = Path(__file__).resolve().parent / "trained" / "energy_predictor.joblib"
MODEL_VERSION = 3
DEFAULT_BUILDING = "College"
DEFAULT_BUILDING_TYPE = "CAMPUS"
FEATURE_COLUMNS = [
    "year",
    "month",
    "building_type",
    "campus_population",
    "is_exam_month",
    "is_study_leave",
    "is_peak_summer",
]


def _estimate_population(year):
    delta = year - BASELINE_YEAR
    return int(round(BASELINE_CAMPUS_POPULATION * ((1 + POPULATION_GROWTH) ** delta)))


def _get_building_type(building_name):
    if not building_name or building_name == DEFAULT_BUILDING:
        return DEFAULT_BUILDING_TYPE

    building = Building.objects.filter(name=building_name).first()
    if not building or not building.building_type:
        return DEFAULT_BUILDING_TYPE

    return building.building_type


def _build_estimator(model_type):
    if model_type == "gradient_boosting":
        return GradientBoostingRegressor(random_state=42)

    return RandomForestRegressor(
        n_estimators=400,
        random_state=42,
    )


def _build_training_pipeline(model_type="random_forest"):
    # building itself is dropped – use only the type to avoid memorizing specific names
    categorical_features = ["building_type"]
    numeric_features = [
        "year",
        "month",
        "campus_population",
        "is_exam_month",
        "is_study_leave",
        "is_peak_summer",
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_features),
            ("numeric", "passthrough", numeric_features),
        ]
    )

    model = _build_estimator(model_type)

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )


def train_energy_model(save_model=True, model_type="random_forest"):
    """
    Train model from historical EnergyConsumption data and optionally save it.
    """
    df = load_energy_consumption_dataframe()

    if df.empty:
        return None

    X = df[FEATURE_COLUMNS].copy()
    y = df["energy_consumed_kwh"].copy()

    pipeline = _build_training_pipeline(model_type=model_type)
    pipeline.fit(X, y)

    if save_model:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            "model": pipeline,
            "feature_columns": FEATURE_COLUMNS,
            "default_building": DEFAULT_BUILDING,
            "model_type": model_type,
            "trained_rows": len(df),
            "model_version": MODEL_VERSION,
        }
        joblib.dump(metadata, MODEL_PATH)

    return pipeline


def load_or_train_model(model_type="random_forest"):
    if MODEL_PATH.exists():
        payload = joblib.load(MODEL_PATH)
        if (
            payload.get("feature_columns") == FEATURE_COLUMNS and
            payload.get("model_version") == MODEL_VERSION
        ):
            return payload

    pipeline = train_energy_model(save_model=True, model_type=model_type)
    if pipeline is None:
        return None

    return joblib.load(MODEL_PATH)


def _build_prediction_frame(year, building, campus_population=None, month=None):
    building_name = building or DEFAULT_BUILDING
    building_type = _get_building_type(building_name)
    population = campus_population if campus_population is not None else _estimate_population(year)

    rows = []
    months = [int(month)] if month is not None else list(range(1, 13))
    for target_month in months:
        rows.append(
            {
                "year": int(year),
                "month": target_month,
                # building name still accepted as argument but not used as feature
                "building_type": building_type,
                "campus_population": int(population),
                "is_exam_month": int(target_month in EXAM_FEATURE_MONTHS),
                "is_study_leave": int(target_month in STUDY_LEAVE_FEATURE_MONTHS),
                "is_peak_summer": int(target_month in PEAK_SUMMER_MONTHS),
            }
        )

    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)


def predict_energy_consumption(year, building, campus_population=None, month=None):
    """
    Predict yearly energy consumption, or a single month when month is provided.
    """
    payload = load_or_train_model()
    if payload is None:
        return None

    return _predict_with_payload(payload, year, building, campus_population, month=month)


def predict_energy_for_years(start_year, years, building=DEFAULT_BUILDING, campus_population=None):
    results = []
    for year in range(start_year, start_year + years):
        pred = predict_energy_consumption(year, building, campus_population)
        results.append(
            {
                "year": year,
                "predicted_kwh": round(pred, 2) if pred is not None else None,
            }
        )
    return results


def predict_energy_per_building(year):
    building_predictions = []
    payload = load_or_train_model()
    if payload is None:
        return {
            "building_predictions": [],
            "total_campus_energy": 0.0,
        }

    buildings = Building.objects.filter(is_navigational_only=False)

    for building in buildings:
        predicted = _predict_with_payload(payload, year, building.name, None)
        predicted_kwh = round(predicted, 2) if predicted is not None else 0.0
        study_leave_predictions = [
            _predict_with_payload(payload, year, building.name, None, month=month)
            for month in sorted(STUDY_LEAVE_FEATURE_MONTHS)
        ]
        study_leave_peak_kwh = round(max(study_leave_predictions), 2) if study_leave_predictions else 0.0
        building_predictions.append(
            {
                "building": building.name,
                "building_type": building.building_type,
                "predicted_kwh": predicted_kwh,
                "study_leave_peak_kwh": study_leave_peak_kwh,
                "lat": building.latitude,
                "lng": building.longitude,
            }
        )

    alert_types = {"HOSTEL", "ACADEMIC"}
    alert_candidates = [
        item["study_leave_peak_kwh"]
        for item in building_predictions
        if item["building_type"] in alert_types
    ]
    alert_threshold = 0.0
    if alert_candidates:
        sorted_candidates = sorted(alert_candidates)
        alert_threshold = sorted_candidates[max(0, len(sorted_candidates) - 1)]
        if len(sorted_candidates) > 1:
            alert_threshold = sorted_candidates[max(0, int(len(sorted_candidates) * 0.66))]

    for item in building_predictions:
        is_anomalous = (
            item["building_type"] in alert_types and
            item["study_leave_peak_kwh"] >= alert_threshold and
            item["study_leave_peak_kwh"] > 0
        )
        item["study_leave_alert"] = is_anomalous
        item["study_leave_alert_reason"] = (
            "High study-leave load for a low-occupancy building."
            if is_anomalous else
            ""
        )

    total_campus_energy = round(
        sum(item["predicted_kwh"] for item in building_predictions),
        2,
    )

    return {
        "building_predictions": sorted(
            building_predictions,
            key=lambda item: item["predicted_kwh"],
            reverse=True,
        ),
        "total_campus_energy": total_campus_energy,
    }


def _predict_with_payload(payload, year, building, campus_population, month=None):
    model = payload["model"]
    # the building argument is only used to look up type; the feature set no longer includes building
    prediction_input = _build_prediction_frame(year, building, campus_population, month=month)
    monthly_predictions = model.predict(prediction_input)
    prediction = float(monthly_predictions.sum())
    return max(0.0, prediction)