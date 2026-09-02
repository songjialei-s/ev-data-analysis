"""新能源汽车充电站运营分析。"""

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"
COMPLETED_STATUS = "completed"


def load_data():
    """从脚本所在目录读取基础数据，避免依赖程序启动目录。"""
    return (
        pd.read_csv(DATA_DIR / "stations.csv"),
        pd.read_csv(DATA_DIR / "charging_orders.csv"),
        pd.read_csv(DATA_DIR / "users.csv"),
    )


def clean_orders(orders, stations, users):
    """校验订单并返回适合核心运营分析的已完成订单及质量报告。"""
    cleaned = orders.copy()
    quality_rows = []

    def record(check, mask, action):
        quality_rows.append({"check": check, "count": int(mask.sum()), "action": action})

    # 重复订单会重复计算订单量和收入，因此仅保留首次出现的记录。
    duplicate_mask = cleaned["order_id"].duplicated(keep="first")
    record("duplicate_order_id", duplicate_mask, "exclude duplicate occurrences")

    # 外键不匹配的订单无法可靠归属站点或用户，不进入核心运营分析。
    invalid_station_mask = ~cleaned["station_id"].isin(stations["station_id"])
    invalid_user_mask = ~cleaned["user_id"].isin(users["user_id"])
    record("unknown_station_id", invalid_station_mask, "exclude from core analysis")
    record("unknown_user_id", invalid_user_mask, "exclude from core analysis")

    # 无法解析或缺失的时间不能用于时长和设备利用率计算。
    cleaned["start_time"] = pd.to_datetime(cleaned["start_time"], errors="coerce")
    cleaned["end_time"] = pd.to_datetime(cleaned["end_time"], errors="coerce")
    invalid_datetime_mask = cleaned[["start_time", "end_time"]].isna().any(axis=1)
    record("missing_or_invalid_datetime", invalid_datetime_mask, "exclude from core analysis")

    invalid_duration_mask = (
        cleaned["start_time"].notna()
        & cleaned["end_time"].notna()
        & (cleaned["end_time"] <= cleaned["start_time"])
    )
    record("end_time_not_after_start_time", invalid_duration_mask, "exclude from core analysis")

    nonpositive_kwh_mask = cleaned["charging_kwh"].isna() | (cleaned["charging_kwh"] <= 0)
    negative_amount_mask = cleaned["total_amount"].isna() | (cleaned["total_amount"] < 0)
    record("nonpositive_or_missing_charging_kwh", nonpositive_kwh_mask, "exclude from core analysis")
    record("negative_or_missing_total_amount", negative_amount_mask, "exclude from core analysis")

    # 逐字段报告缺失值；非关键字段缺失不会被无理由删除。
    for column, count in cleaned.isna().sum().items():
        quality_rows.append(
            {
                "check": f"missing_{column}",
                "count": int(count),
                "action": "review; critical fields are excluded from core analysis",
            }
        )

    status_mask = cleaned["order_status"].str.lower().eq(COMPLETED_STATUS)
    record("non_completed_order", ~status_mask, "exclude from core analysis")
    critical_missing_mask = cleaned[
        ["order_id", "station_id", "user_id", "start_time", "end_time"]
    ].isna().any(axis=1)
    valid_mask = ~(
        duplicate_mask
        | invalid_station_mask
        | invalid_user_mask
        | invalid_datetime_mask
        | invalid_duration_mask
        | nonpositive_kwh_mask
        | negative_amount_mask
        | critical_missing_mask
    ) & status_mask

    valid_orders = cleaned.loc[valid_mask].copy()
    valid_orders["charging_duration_hours"] = (
        valid_orders["end_time"] - valid_orders["start_time"]
    ).dt.total_seconds() / 3600
    valid_orders["order_date"] = valid_orders["start_time"].dt.normalize()
    valid_orders["hour"] = valid_orders["start_time"].dt.hour
    valid_orders["day_type"] = valid_orders["start_time"].dt.dayofweek.map(
        lambda value: "weekend" if value >= 5 else "weekday"
    )
    quality_rows.append(
        {
            "check": "valid_completed_orders",
            "count": len(valid_orders),
            "action": "included in core analysis",
        }
    )
    return valid_orders, pd.DataFrame(quality_rows)


def calculate_overall_metrics(valid_orders):
    """计算整体运营指标。"""
    return pd.DataFrame(
        [{
            "total_orders": len(valid_orders),
            "total_charging_kwh": valid_orders["charging_kwh"].sum(),
            "total_revenue": valid_orders["total_amount"].sum(),
            "avg_order_value": valid_orders["total_amount"].mean(),
            "avg_charging_duration_hours": valid_orders["charging_duration_hours"].mean(),
        }]
    ).round(4)


def calculate_station_summary(valid_orders, stations, quality_report):
    """计算站点订单、收益、单桩效率和设备时间利用率。"""
    grouped = valid_orders.groupby("station_id").agg(
        order_count=("order_id", "count"),
        charging_kwh=("charging_kwh", "sum"),
        revenue=("total_amount", "sum"),
        avg_order_value=("total_amount", "mean"),
        avg_charging_duration_hours=("charging_duration_hours", "mean"),
        total_charging_hours=("charging_duration_hours", "sum"),
        first_order_date=("order_date", "min"),
        last_order_date=("order_date", "max"),
    )
    summary = stations.merge(grouped, on="station_id", how="left")
    numeric_columns = [
        "order_count", "charging_kwh", "revenue", "avg_order_value",
        "avg_charging_duration_hours", "total_charging_hours",
    ]
    summary[numeric_columns] = summary[numeric_columns].fillna(0)
    summary["order_count"] = summary["order_count"].astype(int)
    summary["coverage_days"] = (
        summary["last_order_date"] - summary["first_order_date"]
    ).dt.days.add(1).fillna(0).astype(int)

    capacity_days = summary["pile_count"] * summary["coverage_days"]
    capacity_hours = capacity_days * 24
    summary["orders_per_pile"] = (
        summary["order_count"].div(capacity_days.where(capacity_days > 0)).fillna(0)
    )
    summary["revenue_per_pile"] = (
        summary["revenue"].div(summary["pile_count"].where(summary["pile_count"] > 0)).fillna(0)
    )
    raw_utilization = (
        summary["total_charging_hours"].div(capacity_hours.where(capacity_hours > 0)).fillna(0)
    )
    utilization_anomaly = (raw_utilization < 0) | (raw_utilization > 1)
    summary["equipment_utilization_rate"] = raw_utilization.clip(0, 1)
    summary["utilization_anomaly"] = utilization_anomaly
    quality_report.loc[len(quality_report)] = {
        "check": "station_utilization_outside_0_to_1",
        "count": int(utilization_anomaly.sum()),
        "action": "flag and clip displayed rate to the 0-1 range",
    }

    return summary[[
        "station_id", "station_name", "district", "pile_count", "coverage_days",
        "order_count", "charging_kwh", "revenue", "avg_order_value",
        "avg_charging_duration_hours", "orders_per_pile", "revenue_per_pile",
        "equipment_utilization_rate", "utilization_anomaly",
    ]].round(4)


def calculate_time_analysis(valid_orders):
    """计算小时、工作日/周末和日趋势分析。"""
    hourly = (
        valid_orders.groupby("hour")
        .agg(order_count=("order_id", "count"), charging_kwh=("charging_kwh", "sum"), revenue=("total_amount", "sum"))
        .reindex(range(24), fill_value=0).reset_index().round(2)
    )
    day_type = (
        valid_orders.groupby("day_type")
        .agg(order_count=("order_id", "count"), revenue=("total_amount", "sum"))
        .reindex(["weekday", "weekend"], fill_value=0).reset_index().round(2)
    )
    daily = (
        valid_orders.groupby("order_date")
        .agg(order_count=("order_id", "count"), revenue=("total_amount", "sum"))
        .reset_index()
    )
    daily["revenue"] = daily["revenue"].round(2)
    return hourly, day_type, daily


def save_charts(station_summary, hourly_analysis):
    """仅输出第一阶段需要的三张基础图表。"""
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    chart_specs = [
        (station_summary.sort_values("order_count", ascending=False), "station_name", "order_count", "Orders by Station", "Station", "Orders", "station_orders.png"),
        (station_summary.sort_values("revenue", ascending=False), "station_name", "revenue", "Revenue by Station", "Station", "Revenue", "station_revenue.png"),
        (hourly_analysis, "hour", "order_count", "Hourly Order Distribution", "Hour", "Orders", "hourly_orders.png"),
    ]
    for frame, x_column, y_column, title, xlabel, ylabel, filename in chart_specs:
        frame.plot.bar(x=x_column, y=y_column, legend=False, figsize=(9, 5))
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        if x_column == "station_name":
            plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        plt.savefig(CHART_DIR / filename, dpi=150)
        plt.close()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stations, orders, users = load_data()
    valid_orders, quality_report = clean_orders(orders, stations, users)
    overall_metrics = calculate_overall_metrics(valid_orders)
    station_summary = calculate_station_summary(valid_orders, stations, quality_report)
    hourly_analysis, day_type_analysis, daily_analysis = calculate_time_analysis(valid_orders)

    station_summary.to_csv(OUTPUT_DIR / "station_summary.csv", index=False)
    hourly_analysis.to_csv(OUTPUT_DIR / "hourly_analysis.csv", index=False)
    quality_report.to_csv(OUTPUT_DIR / "data_quality_report.csv", index=False)
    save_charts(station_summary, hourly_analysis)

    sections = [
        ("Overall Operating Metrics", overall_metrics),
        ("Station Summary (ranked by orders)", station_summary.sort_values("order_count", ascending=False)),
        ("Hourly Analysis", hourly_analysis),
        ("Weekday vs Weekend", day_type_analysis),
        ("Daily Trend", daily_analysis),
        ("Data Quality Report", quality_report),
    ]
    for title, frame in sections:
        print(f"\n=== {title} ===")
        print(frame.to_string(index=False))
    print(f"\nOutputs written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
