import hashlib
import random

import pandas as pd

from ..models import Building, EnergyConsumption

EXAM_MONTHS = {4, 5, 12}
STUDY_LEAVE_MONTHS = {4, 5}
EXAM_FEATURE_MONTHS = {4, 5, 12}
STUDY_LEAVE_FEATURE_MONTHS = {4, 5}
PEAK_SUMMER_MONTHS = {3, 4, 5}
BASELINE_YEAR = 2025
POPULATION_GROWTH = 0.05
BASELINE_CAMPUS_POPULATION = 3500
# ranges are handled per-year in _synthetic_year_multiplier
# kept only as reference, not used directly
SYNTHETIC_FACTORS = {
    2024: (0.9, 1.05),
    2023: (0.85, 1.1),
}
BUILDING_ENERGY_MULTIPLIERS = {
    "ACADEMIC": 1.0,
    "HOSTEL": 1.25,
    "LIBRARY": 0.85,
    "ADMIN": 0.9,
    "CANTEEN": 0.65,
    "SHOP": 0.5,
    "AUDITORIUM": 1.4,
}


def _estimate_campus_population(year, base_population=BASELINE_CAMPUS_POPULATION):
    delta = year - BASELINE_YEAR
    return int(round(base_population * ((1 + POPULATION_GROWTH) ** delta)))


def _get_building_multiplier(building_type):
    return BUILDING_ENERGY_MULTIPLIERS.get(building_type or "CAMPUS", 1.0)


def _get_feature_flags(month):
    return {
        "is_exam_month": int(month in EXAM_FEATURE_MONTHS),
        "is_study_leave": int(month in STUDY_LEAVE_FEATURE_MONTHS),
        "is_peak_summer": int(month in PEAK_SUMMER_MONTHS),
    }


def _apply_calendar_adjustments(energy_value, month):
    adjusted_energy = float(energy_value)
    flags = _get_feature_flags(month)

    if flags["is_peak_summer"]:
        adjusted_energy *= 1.15

    if flags["is_exam_month"]:
        adjusted_energy *= 0.75

    if flags["is_study_leave"]:
        adjusted_energy *= 0.60

    return adjusted_energy


def _synthetic_noise_multiplier(year, month, building_name):
    seed_input = f"noise:{year}:{month}:{building_name}".encode("utf-8")
    seed = int(hashlib.sha256(seed_input).hexdigest()[:16], 16)
    rng = random.Random(seed)
    return rng.uniform(0.92, 1.08)


def _synthetic_year_multiplier(year, month, building_name):
    # deterministic random scaling based on year
    seed_input = f"yearmul:{year}:{month}:{building_name}".encode("utf-8")
    seed = int(hashlib.sha256(seed_input).hexdigest()[:16], 16)
    rng = random.Random(seed)

    if year == BASELINE_YEAR - 1:  # 2024
        return rng.uniform(0.9, 1.05)
    if year == BASELINE_YEAR - 2:  # 2023
        return rng.uniform(0.85, 1.1)
    return 1.0


def _build_row(record, base_population, synthetic=False):
    building_name = record.building.name if record.building else "College"
    building_type = record.building.building_type if record.building and record.building.building_type else "CAMPUS"
    feature_flags = _get_feature_flags(int(record.month))

    return {
        "year": int(record.year),
        "month": int(record.month),
        "building": building_name,
        "building_type": building_type,
        "campus_population": _estimate_campus_population(record.year, base_population),
        "is_exam_month": feature_flags["is_exam_month"],
        "is_study_leave": feature_flags["is_study_leave"],
        "is_peak_summer": feature_flags["is_peak_summer"],
        "energy_consumed_kwh": float(record.energy_consumed_kwh),
        "is_synthetic": int(synthetic),
    }


def load_energy_consumption_dataframe(scope=None):
    """
    Load EnergyConsumption data and return ML-ready DataFrame.

    Includes synthetic history for 2023/2024 derived from 2025 where needed.
    """
    queryset = EnergyConsumption.objects.select_related("building")
    if scope:
        queryset = queryset.filter(scope=scope)

    records = list(queryset)

    base_population = BASELINE_CAMPUS_POPULATION

    rows = [_build_row(record, base_population, synthetic=False) for record in records]

    existing_keys = {
        (row["year"], row["month"], row["building"])
        for row in rows
    }

    source_2025 = [record for record in records if record.year == BASELINE_YEAR]
    synthetic_rows = []

    for source in source_2025:
        source_building = source.building.name if source.building else "College"

        # generate synthetic entries for prior years with messy multipliers
        for target_year in (BASELINE_YEAR - 1, BASELINE_YEAR - 2):
            synthetic_key = (target_year, source.month, source_building)
            if synthetic_key in existing_keys:
                continue

            synthetic_record = type("SyntheticRecord", (), {})()
            synthetic_record.year = target_year
            synthetic_record.month = source.month
            synthetic_record.building = source.building
            building_type = source.building.building_type if source.building else "CAMPUS"
            building_name = source.building.name if source.building else "College"

            year_multiplier = _synthetic_year_multiplier(target_year, source.month, building_name)
            building_multiplier = _get_building_multiplier(building_type)
            noise_multiplier = _synthetic_noise_multiplier(target_year, source.month, building_name)

            synthetic_energy = (
                float(source.energy_consumed_kwh)
                * year_multiplier
                * building_multiplier
                * noise_multiplier
            )
            synthetic_record.energy_consumed_kwh = _apply_calendar_adjustments(synthetic_energy, source.month)

            synthetic_rows.append(_build_row(synthetic_record, base_population, synthetic=True))
            existing_keys.add(synthetic_key)

    all_rows = rows + synthetic_rows

    if not all_rows:
        return pd.DataFrame(
            columns=[
                "year",
                "month",
                "building",
                "building_type",
                "campus_population",
                "is_exam_month",
                "is_study_leave",
                "is_peak_summer",
                "energy_consumed_kwh",
                "is_synthetic",
            ]
        )

    df = pd.DataFrame(all_rows)
    df = df.sort_values(["year", "month", "building"]).reset_index(drop=True)
    return df