"""Create Power BI-ready star-schema exports from validated phase-two results."""

from pathlib import Path

import pandas as pd


FACT_COLUMNS = [
    "order_id",
    "station_id",
    "user_id",
    "date",
    "start_time",
    "end_time",
    "hour",
    "weekday",
    "is_weekend",
    "charging_duration_hours",
    "charging_kwh",
    "charging_fee",
    "service_fee",
    "total_amount",
]


def build_fact_orders(valid_orders):
    """Build an order-grain fact table from clean completed charging events."""
    fact = valid_orders.copy()
    fact["date"] = fact["start_time"].dt.normalize()
    fact["weekday"] = fact["start_time"].dt.dayofweek + 1
    fact["is_weekend"] = fact["start_time"].dt.dayofweek >= 5
    return fact[FACT_COLUMNS].sort_values(["start_time", "order_id"]).reset_index(drop=True)


def build_station_dimension(stations):
    """Build the station dimension without changing source attributes."""
    columns = [
        "station_id",
        "station_name",
        "district",
        "pile_count",
        "fast_pile_count",
        "slow_pile_count",
        "open_date",
    ]
    return stations[columns].sort_values("station_id").reset_index(drop=True)


def build_user_dimension(users, user_summary):
    """Attach the phase-two frequency segment to each user dimension row."""
    segments = user_summary[["user_id", "frequency_segment"]].rename(
        columns={"frequency_segment": "user_segment"}
    )
    return (
        users.merge(segments, on="user_id", how="left", validate="one_to_one")
        [["user_id", "register_date", "user_type", "user_segment"]]
        .sort_values("user_id")
        .reset_index(drop=True)
    )


def build_date_dimension(fact_orders):
    """Build one row per calendar date across the complete fact date range."""
    dates = pd.date_range(fact_orders["date"].min(), fact_orders["date"].max(), freq="D")
    dim_date = pd.DataFrame({"date": dates})
    dim_date["year"] = dim_date["date"].dt.year
    dim_date["month"] = dim_date["date"].dt.month
    dim_date["month_name"] = dim_date["date"].dt.month_name()
    dim_date["day"] = dim_date["date"].dt.day
    dim_date["weekday"] = dim_date["date"].dt.dayofweek + 1
    dim_date["weekday_name"] = dim_date["date"].dt.day_name()
    dim_date["is_weekend"] = dim_date["date"].dt.dayofweek >= 5
    return dim_date


def build_station_kpi(station_classification):
    """Select and rename phase-two station metrics without recalculation."""
    kpi = station_classification[[
        "station_id",
        "station_name",
        "order_count",
        "charging_kwh",
        "revenue",
        "avg_order_value",
        "avg_charging_duration_hours",
        "orders_per_pile",
        "revenue_per_pile",
        "equipment_utilization_rate",
        "station_type",
    ]].copy()
    return kpi.rename(
        columns={
            "avg_charging_duration_hours": "avg_charging_duration",
            "station_type": "station_classification",
        }
    ).sort_values("station_id").reset_index(drop=True)


def validate_model(fact, dim_station, dim_user, dim_date, station_kpi, fee_tolerance=0.01):
    """Return explicit PASS/FAIL checks for keys, row counts, and reconciliations."""
    checks = []

    def add_check(name, actual, expected, passed):
        checks.append(
            {
                "check": name,
                "status": "PASS" if passed else "FAIL",
                "actual": actual,
                "expected": expected,
            }
        )

    duplicate_orders = int(fact["order_id"].duplicated().sum())
    unmatched_stations = int((~fact["station_id"].isin(dim_station["station_id"])).sum())
    unmatched_users = int((~fact["user_id"].isin(dim_user["user_id"])).sum())
    unmatched_dates = int((~fact["date"].isin(dim_date["date"])).sum())
    missing_keys = int(fact[["station_id", "user_id"]].isna().any(axis=1).sum())
    duplicate_dates = int(dim_date["date"].duplicated().sum())
    fact_kwh = round(float(fact["charging_kwh"].sum()), 2)
    kpi_kwh = round(float(station_kpi["charging_kwh"].sum()), 2)
    fact_revenue = round(float(fact["total_amount"].sum()), 2)
    kpi_revenue = round(float(station_kpi["revenue"].sum()), 2)
    max_fee_difference = float(
        (fact["charging_fee"] + fact["service_fee"] - fact["total_amount"]).abs().max()
    )

    add_check("fact_order_id_unique", duplicate_orders, 0, duplicate_orders == 0)
    add_check("fact_station_id_matches_dim_station", unmatched_stations, 0, unmatched_stations == 0)
    add_check("fact_user_id_matches_dim_user", unmatched_users, 0, unmatched_users == 0)
    add_check("fact_date_matches_dim_date", unmatched_dates, 0, unmatched_dates == 0)
    add_check("fact_order_count", len(fact), 180, len(fact) == 180)
    add_check("fact_charging_kwh_matches_phase_two", fact_kwh, kpi_kwh, fact_kwh == kpi_kwh)
    add_check("fact_revenue_matches_phase_two", fact_revenue, kpi_revenue, fact_revenue == kpi_revenue)
    add_check(
        "fee_components_match_total",
        round(max_fee_difference, 6),
        f"<= {fee_tolerance}",
        max_fee_difference <= fee_tolerance,
    )
    add_check("fact_station_user_keys_not_null", missing_keys, 0, missing_keys == 0)
    add_check("dim_date_date_unique", duplicate_dates, 0, duplicate_dates == 0)
    return pd.DataFrame(checks)


def export_powerbi_model(
    valid_orders,
    stations,
    users,
    user_summary,
    station_classification,
    output_dir,
):
    """Create, validate, and export the complete Power BI data layer."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fact = build_fact_orders(valid_orders)
    dim_station = build_station_dimension(stations)
    dim_user = build_user_dimension(users, user_summary)
    dim_date = build_date_dimension(fact)
    station_kpi = build_station_kpi(station_classification)
    validation = validate_model(fact, dim_station, dim_user, dim_date, station_kpi)

    fact_export = fact.copy()
    fact_export["date"] = fact_export["date"].dt.strftime("%Y-%m-%d")
    for column in ("start_time", "end_time"):
        fact_export[column] = fact_export[column].dt.strftime("%Y-%m-%d %H:%M:%S")
    fact_export["charging_duration_hours"] = fact_export["charging_duration_hours"].round(4)

    date_export = dim_date.copy()
    date_export["date"] = date_export["date"].dt.strftime("%Y-%m-%d")

    exports = {
        "fact_charging_orders.csv": fact_export,
        "dim_station.csv": dim_station,
        "dim_user.csv": dim_user,
        "dim_date.csv": date_export,
        "station_kpi.csv": station_kpi,
        "model_validation.csv": validation,
    }
    for filename, frame in exports.items():
        frame.to_csv(output_dir / filename, index=False)

    failed_checks = validation.loc[validation["status"] != "PASS", "check"].tolist()
    if failed_checks:
        raise ValueError(f"Power BI model validation failed: {', '.join(failed_checks)}")

    return {
        "fact_rows": len(fact),
        "station_rows": len(dim_station),
        "user_rows": len(dim_user),
        "date_rows": len(dim_date),
        "validation_checks": len(validation),
    }
