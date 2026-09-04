"""Run the real-order SQL layer and validate metric conservation.

Input is the private clean fact CSV. Row-level source identifiers are loaded only
into an ignored local SQLite database. Published station and user identifiers are
replaced with non-reversible analysis codes before CSV export.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SQL_FILES = [
    "01_overview.sql", "02_station_analysis.sql", "03_time_analysis.sql",
    "04_revenue_analysis.sql", "05_user_analysis.sql",
    "06_end_reason_analysis.sql", "07_data_quality_analysis.sql",
]
ALIASES = {
    "order_num": "orderNum", "station_name": "stationName", "plug_num": "plugNum",
    "charge_begin": "chargeBegin", "charge_end": "chargeEnd",
    "charge_time_minutes": "chargeTimeMinute", "begin_soc": "beginSOC",
    "end_soc": "endSOC", "end_reason": "endReason",
    "charging_kwh": "chargingPower", "gross_amount": "chargingPay",
    "electricity_amount": "chargingelectricityPay", "service_amount": "chargingServicePay",
    "actual_amount": "chargingPayActual", "discount_amount": "chargingDiscount",
    "pay_status": "payStatus",
}
REQUIRED = {
    "orderNum", "stationName", "plugNum", "chargeBegin", "chargeEnd",
    "chargingPower", "chargingPay", "chargingPayActual", "chargingelectricityPay",
    "chargingServicePay", "chargingDiscount", "duration_minutes_calculated",
    "beginSOC", "endSOC", "endReason", "user_key",
}


def read_clean_fact(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False).rename(columns=ALIASES)
    missing = REQUIRED.difference(frame.columns)
    if missing:
        raise ValueError(f"Clean fact is missing required columns: {sorted(missing)}")

    frame["chargeBegin"] = pd.to_datetime(frame["chargeBegin"], errors="coerce")
    frame["chargeEnd"] = pd.to_datetime(frame["chargeEnd"], errors="coerce")
    for column in [
        "chargingPower", "chargingPay", "chargingPayActual", "chargingelectricityPay",
        "chargingServicePay", "chargingDiscount", "duration_minutes_calculated",
        "beginSOC", "endSOC",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    truthy = {"是", "true", "1", "yes"}
    if "is_paid" in frame:
        frame["is_paid"] = frame["is_paid"].astype(str).str.strip().str.lower().isin(truthy).astype(int)
    else:
        frame["is_paid"] = frame["payStatus"].eq("已支付").astype(int)
    if "is_zero_energy_session" in frame:
        frame["is_zero_energy_session"] = (
            frame["is_zero_energy_session"].astype(str).str.strip().str.lower().isin(truthy).astype(int)
        )
    else:
        frame["is_zero_energy_session"] = frame["chargingPower"].fillna(0).le(0).astype(int)

    frame["charge_date"] = frame["chargeBegin"].dt.strftime("%Y-%m-%d")
    frame["charge_month"] = frame["chargeBegin"].dt.strftime("%Y-%m")
    frame["charge_hour"] = frame["chargeBegin"].dt.hour
    frame["weekday_number"] = frame["chargeBegin"].dt.weekday + 1
    weekday_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}
    frame["weekday_name"] = frame["weekday_number"].map(weekday_names)
    frame["day_type"] = frame["weekday_number"].ge(6).map({True: "weekend", False: "weekday"})
    frame["end_reason_category"] = "待业务确认"
    return frame


def named_queries(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^-- name:\s*([a-z0-9_]+)\s*$", text))
    queries = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        query = text[start:end].strip()
        if query:
            queries.append((match.group(1), query))
    if not queries:
        raise ValueError(f"No named SQL queries found in {path}")
    return queries


def privacy_safe(result: pd.DataFrame, station_codes: dict[str, str]) -> pd.DataFrame:
    result = result.copy()
    if "stationName" in result:
        result.insert(0, "station_code", result["stationName"].map(station_codes))
        result = result.drop(columns="stationName")
    if "user_key" in result:
        ordered = sorted(result["user_key"].dropna().astype(str).unique())
        user_codes = {key: f"ANON_USER_{index:05d}" for index, key in enumerate(ordered, 1)}
        result.insert(0, "anonymous_user_id", result["user_key"].astype(str).map(user_codes))
        result = result.drop(columns="user_key")
    return result


def validation_row(name: str, expected: float, actual: float, tolerance: float) -> dict[str, object]:
    difference = abs(float(expected) - float(actual))
    return {
        "check_name": name,
        "python_value": round(float(expected), 6),
        "sql_value": round(float(actual), 6),
        "difference": round(difference, 6),
        "tolerance": tolerance,
        "status": "PASS" if difference <= tolerance else "FAIL",
    }


def build_metric_validation(frame: pd.DataFrame, results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    overview = results["overview"].iloc[0]
    rows = [
        validation_row("sql_total_orders_equals_clean_rows", len(frame), overview["total_orders"], 0),
        validation_row("station_orders_sum_equals_total", overview["total_orders"], results["station_analysis"]["order_count"].sum(), 0),
        validation_row("monthly_orders_sum_equals_total", overview["total_orders"], results["monthly_analysis"]["order_count"].sum(), 0),
        validation_row("hourly_orders_sum_equals_total", overview["total_orders"], results["hourly_analysis"]["order_count"].sum(), 0),
        validation_row("total_charging_kwh", frame["chargingPower"].sum(), overview["total_charging_kwh"], 0.001),
        validation_row("total_amount_due", frame["chargingPay"].sum(), overview["total_amount_due"], 0.01),
        validation_row("total_amount_paid", frame.loc[frame["is_paid"].eq(1), "chargingPayActual"].sum(), overview["total_amount_paid"], 0.01),
        validation_row("electricity_plus_service_equals_due", overview["total_amount_due"], overview["total_electricity_fee"] + overview["total_service_fee"], 0.01),
        validation_row("user_order_sum_equals_orders_with_user", frame.loc[frame["user_key"].notna(), "orderNum"].nunique(), results["user_analysis"]["order_count"].sum(), 0),
        validation_row("end_reason_orders_equal_nonnull_reason_orders", frame.loc[frame["endReason"].notna(), "orderNum"].nunique(), results["end_reason_analysis"]["order_count"].sum(), 0),
    ]
    return pd.DataFrame(rows)


def write_findings(output_dir: Path, results: dict[str, pd.DataFrame], station_codes: dict[str, str]) -> None:
    overview = results["overview"].iloc[0]
    station = results["station_analysis"].sort_values("order_count", ascending=False).iloc[0]
    station_paid = results["station_analysis"].sort_values("amount_paid", ascending=False).iloc[0]
    hour = results["hourly_analysis"].sort_values("order_count", ascending=False).iloc[0]
    reason = results["end_reason_analysis"].sort_values("order_count", ascending=False).iloc[0]
    user_distribution = results["user_order_distribution"]
    single_user_share = float(user_distribution.loc[user_distribution["order_count"].eq(1), "user_share"].sum())
    max_user_orders = int(results["user_analysis"]["order_count"].max())
    validation = results["metric_validation"]
    station_code = station_codes[str(station["stationName"])]
    lines = [
        "# SQL 阶段初步发现", "", "## 数据事实", "",
        f"- 可信事实表包含 {int(overview['total_orders']):,} 笔订单，总充电量为 {overview['total_charging_kwh']:,.3f} kWh。",
        f"- 总应付金额为 {overview['total_amount_due']:,.2f}，已支付订单总实付金额为 {overview['total_amount_paid']:,.2f}。币种待业务确认。",
        f"- 期间活跃用户 {int(overview['active_users']):,} 个；期间出现过的站点—枪口组合 {int(overview['active_plugs']):,} 个，后者不是配置枪数。",
        f"- 订单量最高的匿名站点为 {station_code}，订单数 {int(station['order_count']):,}。",
        f"- 实付金额最高的匿名站点为 {station_codes[str(station_paid['stationName'])]}，实付金额 {station_paid['amount_paid']:,.2f}。",
        f"- 订单开始最集中的小时为 {int(hour['hour']):02d}:00，订单数 {int(hour['order_count']):,}。",
        f"- {single_user_share:.2%} 的脱敏用户在数据期间仅出现 1 笔订单；单个脱敏用户最多出现 {max_user_orders:,} 笔订单。",
        f"- 最常见原始停止原因为“{reason['endReason']}”，占可信订单 {float(reason['order_share']):.2%}。该文本尚未归类为正常或异常。",
        "", "## 初步判断", "",
        "- 站点、小时与停止原因存在集中度差异，可作为下一轮钻取顺序；当前结果本身不足以支持扩容、停运或责任归因。",
        "- 应付、实付、电费和服务费已分别计算，可以进一步检查支付差额与收益结构，但不能把应付金额称为到账收入。",
        "- 极高订单频次的脱敏用户可能对应共享账号、企业账号或其他业务形态，需要确认后才能解释为个人复购。",
        "", "## 待业务确认", "",
        "- 停止原因的正常/用户/车辆/设备/平台/通信分类及设备侧边界。",
        "- 金额币种、退款/冲正/部分支付和跨期支付口径。",
        "- 峰谷平字段对应的实际计费时段，以及 chargingPower 的正式单位。",
        "- 站点名称及聚合运营结果是否允许对外公开。当前文件已使用匿名站点代码。",
        "- 数据起止月份不是完整自然月，月度规模不得直接与完整月份作同比式比较。",
        "", "## 一致性验证", "",
        f"- {int((validation['status'] == 'PASS').sum())}/{len(validation)} 项验证通过；容差见 `metric_validation.csv`。",
    ]
    (output_dir / "preliminary_findings.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean_csv", type=Path, help="Private clean_charging_orders.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "sql")
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "private_processed" / "real_analysis.db")
    args = parser.parse_args()

    frame = read_clean_fact(args.clean_csv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.database.parent.mkdir(parents=True, exist_ok=True)
    station_names = sorted(frame["stationName"].dropna().astype(str).unique())
    station_codes = {name: f"STATION_{index:02d}" for index, name in enumerate(station_names, 1)}

    with sqlite3.connect(args.database) as connection:
        frame.to_sql("clean_charging_orders", connection, if_exists="replace", index=False)
        results: dict[str, pd.DataFrame] = {}
        for filename in SQL_FILES:
            for name, query in named_queries(ROOT / "sql" / filename):
                results[name] = pd.read_sql_query(query, connection)

    validation = build_metric_validation(frame, results)
    results["metric_validation"] = validation
    for name, result in results.items():
        privacy_safe(result, station_codes).to_csv(
            args.output_dir / f"{name}.csv", index=False, encoding="utf-8-sig"
        )
    write_findings(args.output_dir, results, station_codes)

    failed = validation.loc[validation["status"].ne("PASS"), "check_name"].tolist()
    print(f"rows={len(frame)} queries={len(results) - 1} validations={len(validation)} failed={failed}")
    print(f"output_dir={args.output_dir.resolve()}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
