"""EV charging station operations analysis: phase two."""

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from db import run_all_sql, write_analysis_database
from powerbi import export_powerbi_model


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
POWERBI_OUTPUT_DIR = OUTPUT_DIR / "powerbi"
CHART_DIR = OUTPUT_DIR / "charts"
SQL_DIR = BASE_DIR / "sql"
DATABASE_PATH = BASE_DIR / "ev_charging.db"
COMPLETED_STATUS = "completed"
FEE_TOLERANCE = 0.01


def load_data():
    """Load source CSV files relative to this script, not the current shell directory."""
    return (
        pd.read_csv(DATA_DIR / "stations.csv"),
        pd.read_csv(DATA_DIR / "charging_orders.csv"),
        pd.read_csv(DATA_DIR / "users.csv"),
    )


def clean_orders(orders, stations, users):
    """Validate raw orders and retain only reliable completed orders for core analysis."""
    cleaned = orders.copy()
    quality_rows = []

    def record(check, mask, action):
        quality_rows.append({"check": check, "count": int(mask.sum()), "action": action})

    duplicate_mask = cleaned["order_id"].duplicated(keep="first")
    record("duplicate_order_id", duplicate_mask, "exclude duplicate occurrences")

    invalid_station_mask = ~cleaned["station_id"].isin(stations["station_id"])
    invalid_user_mask = ~cleaned["user_id"].isin(users["user_id"])
    record("unknown_station_id", invalid_station_mask, "exclude from core analysis")
    record("unknown_user_id", invalid_user_mask, "exclude from core analysis")

    cleaned["start_time"] = pd.to_datetime(cleaned["start_time"], errors="coerce")
    cleaned["end_time"] = pd.to_datetime(cleaned["end_time"], errors="coerce")
    invalid_datetime_mask = cleaned[["start_time", "end_time"]].isna().any(axis=1)
    invalid_duration_mask = (
        cleaned["start_time"].notna()
        & cleaned["end_time"].notna()
        & (cleaned["end_time"] <= cleaned["start_time"])
    )
    record("missing_or_invalid_datetime", invalid_datetime_mask, "exclude from core analysis")
    record("end_time_not_after_start_time", invalid_duration_mask, "exclude from core analysis")

    money_columns = ["charging_kwh", "charging_fee", "service_fee", "total_amount"]
    for column in money_columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    nonpositive_kwh_mask = cleaned["charging_kwh"].isna() | (cleaned["charging_kwh"] <= 0)
    negative_amount_mask = cleaned["total_amount"].isna() | (cleaned["total_amount"] < 0)
    fee_component_missing = cleaned[["charging_fee", "service_fee", "total_amount"]].isna().any(axis=1)
    fee_mismatch_mask = fee_component_missing | (
        (cleaned["charging_fee"] + cleaned["service_fee"] - cleaned["total_amount"]).abs()
        > FEE_TOLERANCE
    )
    record("nonpositive_or_missing_charging_kwh", nonpositive_kwh_mask, "exclude from core analysis")
    record("negative_or_missing_total_amount", negative_amount_mask, "exclude from core analysis")
    record("fee_components_do_not_match_total", fee_mismatch_mask, "exclude from core analysis")

    for column, count in cleaned.isna().sum().items():
        quality_rows.append(
            {
                "check": f"missing_{column}",
                "count": int(count),
                "action": "review; critical fields are excluded from core analysis",
            }
        )

    status_mask = cleaned["order_status"].fillna("").str.lower().eq(COMPLETED_STATUS)
    record("non_completed_order", ~status_mask, "exclude from core analysis")
    critical_missing_mask = cleaned[
        ["order_id", "station_id", "user_id", "start_time", "end_time"]
    ].isna().any(axis=1)
    invalid_mask = (
        duplicate_mask
        | invalid_station_mask
        | invalid_user_mask
        | invalid_datetime_mask
        | invalid_duration_mask
        | nonpositive_kwh_mask
        | negative_amount_mask
        | fee_mismatch_mask
        | critical_missing_mask
    )
    valid_orders = cleaned.loc[~invalid_mask & status_mask].copy()
    valid_orders["charging_duration_hours"] = (
        valid_orders["end_time"] - valid_orders["start_time"]
    ).dt.total_seconds() / 3600
    valid_orders["order_date"] = valid_orders["start_time"].dt.normalize()
    valid_orders["hour"] = valid_orders["start_time"].dt.hour
    valid_orders["day_type"] = valid_orders["start_time"].dt.dayofweek.map(
        lambda value: "weekend" if value >= 5 else "weekday"
    )
    quality_rows.append(
        {"check": "valid_completed_orders", "count": len(valid_orders), "action": "included in core analysis"}
    )
    return valid_orders, pd.DataFrame(quality_rows)


def calculate_overall_metrics(valid_orders, users):
    """Calculate operation and user headline metrics."""
    active_users = valid_orders["user_id"].nunique()
    return pd.DataFrame([{
        "total_orders": len(valid_orders),
        "total_users": len(users),
        "active_users": active_users,
        "total_charging_kwh": valid_orders["charging_kwh"].sum(),
        "total_revenue": valid_orders["total_amount"].sum(),
        "avg_order_value": valid_orders["total_amount"].mean(),
        "avg_charging_duration_hours": valid_orders["charging_duration_hours"].mean(),
        "avg_orders_per_active_user": len(valid_orders) / active_users if active_users else 0,
        "avg_revenue_per_active_user": valid_orders["total_amount"].sum() / active_users if active_users else 0,
    }]).round(4)


def calculate_station_summary(valid_orders, stations, quality_report):
    """Calculate comparable multi-dimensional station operating metrics."""
    coverage_days = max(
        1,
        (valid_orders["order_date"].max() - valid_orders["order_date"].min()).days + 1,
    )
    grouped = valid_orders.groupby("station_id").agg(
        order_count=("order_id", "count"),
        charging_kwh=("charging_kwh", "sum"),
        charging_fee_revenue=("charging_fee", "sum"),
        service_fee_revenue=("service_fee", "sum"),
        revenue=("total_amount", "sum"),
        avg_order_value=("total_amount", "mean"),
        avg_charging_duration_hours=("charging_duration_hours", "mean"),
        total_charging_hours=("charging_duration_hours", "sum"),
    )
    summary = stations.merge(grouped, on="station_id", how="left")
    numeric = list(grouped.columns)
    summary[numeric] = summary[numeric].fillna(0)
    summary["order_count"] = summary["order_count"].astype(int)
    summary["coverage_days"] = coverage_days
    pile_days = summary["pile_count"] * coverage_days
    capacity_hours = pile_days * 24
    summary["orders_per_pile"] = summary["order_count"].div(pile_days.where(pile_days > 0)).fillna(0)
    summary["revenue_per_pile"] = summary["revenue"].div(summary["pile_count"].where(summary["pile_count"] > 0)).fillna(0)
    summary["revenue_per_kwh"] = summary["revenue"].div(summary["charging_kwh"].where(summary["charging_kwh"] > 0)).fillna(0)
    raw_utilization = summary["total_charging_hours"].div(capacity_hours.where(capacity_hours > 0)).fillna(0)
    utilization_anomaly = (raw_utilization < 0) | (raw_utilization > 1)
    summary["equipment_utilization_rate"] = raw_utilization.clip(0, 1)
    summary["utilization_anomaly"] = utilization_anomaly
    quality_report.loc[len(quality_report)] = {
        "check": "station_utilization_outside_0_to_1",
        "count": int(utilization_anomaly.sum()),
        "action": "flag and clip displayed rate to the 0-1 range",
    }
    return summary.round(4)


def classify_stations(station_summary):
    """Classify stations dynamically with medians and upper quartiles, never names."""
    classified = station_summary.copy()
    medians = classified[
        ["orders_per_pile", "revenue_per_pile", "revenue", "equipment_utilization_rate"]
    ].median()
    high_utilization = classified["equipment_utilization_rate"].quantile(0.75)

    def classify(row):
        if (
            row["equipment_utilization_rate"] >= high_utilization
            and row["orders_per_pile"] >= medians["orders_per_pile"]
        ):
            return "high_load_expansion_candidate"
        if (
            row["orders_per_pile"] >= medians["orders_per_pile"]
            and row["revenue_per_pile"] >= medians["revenue_per_pile"]
            and row["revenue"] >= medians["revenue"]
        ):
            return "efficient_core_station"
        if (
            row["orders_per_pile"] < medians["orders_per_pile"]
            and row["equipment_utilization_rate"] < medians["equipment_utilization_rate"]
        ):
            return "low_utilization_optimization"
        return "stable_station"

    classified["station_type"] = classified.apply(classify, axis=1)
    return classified


def calculate_user_summary(valid_orders, users):
    """Rank users and segment frequency using thresholds suited to this sample."""
    metrics = valid_orders.groupby("user_id").agg(
        order_count=("order_id", "count"),
        total_revenue=("total_amount", "sum"),
        total_charging_kwh=("charging_kwh", "sum"),
        avg_order_value=("total_amount", "mean"),
    )
    summary = users.merge(metrics, on="user_id", how="left")
    metric_columns = ["order_count", "total_revenue", "total_charging_kwh", "avg_order_value"]
    summary[metric_columns] = summary[metric_columns].fillna(0)
    summary["order_count"] = summary["order_count"].astype(int)
    summary["frequency_segment"] = pd.cut(
        summary["order_count"], bins=[-1, 5, 11, float("inf")],
        labels=["low_frequency", "medium_frequency", "high_frequency"],
    ).astype(str)
    return summary.sort_values(["order_count", "total_revenue"], ascending=False).round(2)


def calculate_revenue_analysis(station_summary):
    """Describe station income structure and demand/value combinations."""
    revenue = station_summary[[
        "station_id", "station_name", "pile_count", "order_count",
        "charging_fee_revenue", "service_fee_revenue", "revenue",
        "revenue_per_pile", "avg_order_value", "revenue_per_kwh",
    ]].copy()
    revenue["service_fee_share"] = (
        revenue["service_fee_revenue"].div(revenue["revenue"].where(revenue["revenue"] > 0)).fillna(0)
    )
    median_orders = revenue["order_count"].median()
    median_revenue = revenue["revenue"].median()
    median_order_value = revenue["avg_order_value"].median()

    def pattern(row):
        if row["order_count"] >= median_orders and row["revenue"] >= median_revenue:
            return "high_orders_high_revenue"
        if row["order_count"] >= median_orders and row["avg_order_value"] < median_order_value:
            return "high_orders_low_avg_value"
        if row["order_count"] < median_orders and row["avg_order_value"] >= median_order_value:
            return "low_orders_high_avg_value"
        return "low_orders_low_revenue"

    revenue["revenue_pattern"] = revenue.apply(pattern, axis=1)
    return revenue.sort_values("revenue", ascending=False).round(4)


def calculate_time_analysis(valid_orders):
    """Calculate complete 24-hour, weekday/weekend, and daily demand views."""
    hourly = (
        valid_orders.groupby("hour")
        .agg(order_count=("order_id", "count"), charging_kwh=("charging_kwh", "sum"), revenue=("total_amount", "sum"))
        .reindex(range(24), fill_value=0).reset_index().round(2)
    )
    day_type = valid_orders.groupby("day_type").agg(
        order_count=("order_id", "count"),
        revenue=("total_amount", "sum"),
        avg_order_value=("total_amount", "mean"),
        active_days=("order_date", "nunique"),
    ).reindex(["weekday", "weekend"], fill_value=0).reset_index()
    day_type["avg_daily_orders"] = day_type["order_count"].div(day_type["active_days"].where(day_type["active_days"] > 0)).fillna(0)
    daily = valid_orders.groupby("order_date").agg(
        order_count=("order_id", "count"), revenue=("total_amount", "sum")
    ).reset_index()
    return hourly, day_type.round(2), daily.round({"revenue": 2})


def build_business_insights(overall, station_classification, user_summary, hourly, day_type):
    """Create a reproducible narrative whose statements are traceable to calculated results."""
    metrics = overall.iloc[0]
    by_orders = station_classification.nlargest(1, "order_count").iloc[0]
    by_revenue = station_classification.nlargest(1, "revenue").iloc[0]
    by_utilization = station_classification.nlargest(1, "equipment_utilization_rate").iloc[0]
    by_revenue_per_pile = station_classification.nlargest(1, "revenue_per_pile").iloc[0]
    high_users = user_summary[user_summary["frequency_segment"] == "high_frequency"]
    high_order_share = high_users["order_count"].sum() / max(user_summary["order_count"].sum(), 1)
    high_revenue_share = high_users["total_revenue"].sum() / max(user_summary["total_revenue"].sum(), 1)
    peak_hours = hourly.nlargest(3, "order_count")["hour"].astype(int).sort_values().tolist()
    weekday = day_type.set_index("day_type").loc["weekday"]
    weekend = day_type.set_index("day_type").loc["weekend"]

    low = station_classification[station_classification["station_type"] == "low_utilization_optimization"]
    expansion = station_classification[station_classification["station_type"] == "high_load_expansion_candidate"]
    median_revenue_per_pile = station_classification["revenue_per_pile"].median()
    weak_revenue = station_classification[
        (station_classification["order_count"] > station_classification["order_count"].median())
        & (station_classification["revenue_per_pile"] < median_revenue_per_pile)
    ]

    def station_list(frame):
        return ", ".join(frame["station_name"].tolist()) if not frame.empty else "None identified"

    lines = [
        "# Business Insights",
        "",
        "## Operating Overview",
        "",
        f"- Valid completed orders: **{int(metrics['total_orders'])}**.",
        f"- Active users: **{int(metrics['active_users'])}** of {int(metrics['total_users'])} registered users.",
        f"- Total charging volume: **{metrics['total_charging_kwh']:.1f} kWh**.",
        f"- Total revenue: **{metrics['total_revenue']:.2f}**.",
        "",
        "## Station Performance",
        "",
        f"- Most orders: **{by_orders['station_name']}** ({int(by_orders['order_count'])} orders).",
        f"- Highest revenue: **{by_revenue['station_name']}** ({by_revenue['revenue']:.2f}).",
        f"- Highest equipment utilization: **{by_utilization['station_name']}** ({by_utilization['equipment_utilization_rate']:.2%}).",
        f"- Highest revenue per pile: **{by_revenue_per_pile['station_name']}** ({by_revenue_per_pile['revenue_per_pile']:.2f}).",
        "",
        "## User Analysis",
        "",
        f"- High-frequency users (12+ orders): **{len(high_users)}**.",
        f"- Their order contribution is **{high_order_share:.1%}** and revenue contribution is **{high_revenue_share:.1%}**.",
        "",
        "## Time Patterns",
        "",
        f"- The three highest-demand start hours are **{', '.join(f'{h:02d}:00' for h in peak_hours)}**.",
        f"- Average daily orders are **{weekday['avg_daily_orders']:.2f}** on weekdays and **{weekend['avg_daily_orders']:.2f}** on weekends.",
        "",
        "## Anomaly and Opportunity Stations",
        "",
        f"- Low-utilization optimization candidates: **{station_list(low)}**.",
        f"- High-load expansion candidates: **{station_list(expansion)}**.",
        f"- High-order but below-median revenue-per-pile stations: **{station_list(weak_revenue)}**.",
        "",
        "## Business Recommendations",
        "",
    ]
    if not expansion.empty:
        lines.append(f"- For **{station_list(expansion)}**, review peak-hour queues and assess incremental pile capacity because both utilization and per-pile demand are relatively high.")
    if not low.empty:
        lines.append(f"- For **{station_list(low)}**, investigate location traffic, pricing, visibility, and promotion before adding equipment because demand and utilization are both below peer medians.")
    if not weak_revenue.empty:
        lines.append(f"- For **{station_list(weak_revenue)}**, review charging mix and fee structure: traffic is above median but revenue efficiency per pile is below median.")
    lines.append("- Treat these findings as directional because the repository uses synthetic sample data; validate actions with real queue, availability, and local traffic data before investment decisions.")
    return "\n".join(lines) + "\n"


def save_charts(user_summary, station_classification, revenue_analysis, hourly):
    """Refresh phase-one charts and create three decision-oriented phase-two charts."""
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    station_classification.sort_values("order_count", ascending=False).plot.bar(
        x="station_name", y="order_count", legend=False, figsize=(10, 5), color="#4C78A8"
    )
    plt.title("Orders by Station")
    plt.xlabel("Station")
    plt.ylabel("Orders")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(CHART_DIR / "station_orders.png", dpi=150)
    plt.close()

    station_classification.sort_values("revenue", ascending=False).plot.bar(
        x="station_name", y="revenue", legend=False, figsize=(10, 5), color="#59A14F"
    )
    plt.title("Revenue by Station")
    plt.xlabel("Station")
    plt.ylabel("Revenue")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(CHART_DIR / "station_revenue.png", dpi=150)
    plt.close()

    hourly.plot.bar(x="hour", y="order_count", legend=False, figsize=(10, 5), color="#F28E2B")
    plt.title("Hourly Order Distribution")
    plt.xlabel("Hour")
    plt.ylabel("Orders")
    plt.tight_layout()
    plt.savefig(CHART_DIR / "hourly_orders.png", dpi=150)
    plt.close()

    users = user_summary.sort_values("order_count", ascending=False)
    users.plot.bar(x="user_id", y="order_count", legend=False, figsize=(10, 5), color="#4C78A8")
    plt.title("User Order Distribution")
    plt.xlabel("User")
    plt.ylabel("Orders")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(CHART_DIR / "user_order_distribution.png", dpi=150)
    plt.close()

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        station_classification["orders_per_pile"],
        station_classification["equipment_utilization_rate"],
        s=station_classification["revenue_per_pile"].clip(lower=1) * 0.35,
        alpha=0.75,
    )
    for _, row in station_classification.iterrows():
        ax.annotate(row["station_id"], (row["orders_per_pile"], row["equipment_utilization_rate"]), xytext=(5, 4), textcoords="offset points")
    ax.set_title("Station Efficiency: Demand vs Utilization")
    ax.set_xlabel("Daily Orders per Pile")
    ax.set_ylabel("Equipment Utilization Rate")
    plt.tight_layout()
    plt.savefig(CHART_DIR / "station_efficiency.png", dpi=150)
    plt.close()

    revenue_analysis.set_index("station_name")[["charging_fee_revenue", "service_fee_revenue"]].plot.bar(
        stacked=True, figsize=(10, 5), color=["#59A14F", "#F28E2B"]
    )
    plt.title("Station Revenue Composition")
    plt.xlabel("Station")
    plt.ylabel("Revenue")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(CHART_DIR / "revenue_comparison.png", dpi=150)
    plt.close()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stations, raw_orders, users = load_data()
    valid_orders, quality_report = clean_orders(raw_orders, stations, users)
    overall = calculate_overall_metrics(valid_orders, users)
    station_summary = calculate_station_summary(valid_orders, stations, quality_report)
    station_classification = classify_stations(station_summary)
    user_summary = calculate_user_summary(valid_orders, users)
    revenue_analysis = calculate_revenue_analysis(station_summary)
    hourly, day_type, daily = calculate_time_analysis(valid_orders)

    write_analysis_database(DATABASE_PATH, stations, users, valid_orders)
    sql_results = run_all_sql(DATABASE_PATH, SQL_DIR)

    station_summary.to_csv(OUTPUT_DIR / "station_summary.csv", index=False)
    hourly.to_csv(OUTPUT_DIR / "hourly_analysis.csv", index=False)
    quality_report.to_csv(OUTPUT_DIR / "data_quality_report.csv", index=False)
    user_summary.to_csv(OUTPUT_DIR / "user_summary.csv", index=False)
    revenue_analysis.to_csv(OUTPUT_DIR / "revenue_analysis.csv", index=False)
    station_classification.to_csv(OUTPUT_DIR / "station_classification.csv", index=False)
    (OUTPUT_DIR / "business_insights.md").write_text(
        build_business_insights(overall, station_classification, user_summary, hourly, day_type),
        encoding="utf-8",
    )
    save_charts(user_summary, station_classification, revenue_analysis, hourly)
    powerbi_summary = export_powerbi_model(
        valid_orders,
        stations,
        users,
        user_summary,
        station_classification,
        POWERBI_OUTPUT_DIR,
    )

    print("\n=== Overall Metrics ===")
    print(overall.to_string(index=False))
    print("\n=== Station Classification ===")
    print(station_classification[["station_id", "station_name", "order_count", "revenue", "orders_per_pile", "equipment_utilization_rate", "station_type"]].to_string(index=False))
    print("\n=== User Frequency Segments ===")
    print(user_summary.groupby("frequency_segment", observed=True).agg(user_count=("user_id", "count"), order_count=("order_count", "sum"), revenue=("total_revenue", "sum")).to_string())
    print("\n=== SQL Validation ===")
    for sql_file, queries in sql_results.items():
        print(f"{sql_file}: " + ", ".join(f"{name}={len(result)} rows" for name, result in queries.items()))
    print(f"\nRaw orders: {len(raw_orders)} | Valid orders: {len(valid_orders)}")
    print("\n=== Power BI Model ===")
    print(
        " | ".join(f"{name}={value}" for name, value in powerbi_summary.items())
    )
    print(f"Database: {DATABASE_PATH}")
    print(f"Outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
