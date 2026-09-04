"""Clean a private charging-order Excel file without publishing raw identifiers.

The source workbook is read-only. The detailed clean fact table is written to a
local ignored directory; only aggregate quality reports are suitable for Git.
Operational exceptions are retained and flagged unless a row cannot represent
a charging session because its primary key or cloud-platform duration is invalid.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd


PRIVATE_COLUMNS = {
    "userNum", "companyName", "cardNum", "carLicense", "carVin",
    "carMyLicense", "carDept", "deptName", "businessNum",
}
TIME_COLUMNS = ["chargeBegin", "chargeEnd", "chargeBeginNative", "chargeEndNative", "payTime"]
NUMERIC_COLUMNS = [
    "chargeTimeMinute", "chargeTimeNative", "beginSOC", "endSOC",
    "chargingPower", "chargingPay", "chargingelectricityPay",
    "chargingServicePay", "chargingPayActual", "chargingDiscount",
]


def pseudonym(value: object, namespace: str, salt: str) -> object:
    """Return a stable local analysis key; the salt must never be committed."""
    if pd.isna(value) or not str(value).strip():
        return pd.NA
    payload = f"{salt}|{namespace}|{str(value).strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def load_orders(source: Path) -> pd.DataFrame:
    orders = pd.read_excel(source, dtype=object)
    orders.columns = orders.columns.astype(str).str.strip()
    required = {"orderNum", "chargeBegin", "chargeEnd", "chargeTimeMinute", "chargingPower", "endReason"}
    missing = required.difference(orders.columns)
    if missing:
        raise ValueError(f"Missing required source columns: {sorted(missing)}")
    for column in TIME_COLUMNS:
        if column in orders:
            orders[column] = pd.to_datetime(orders[column], errors="coerce")
    for column in NUMERIC_COLUMNS:
        if column in orders:
            orders[column] = pd.to_numeric(orders[column], errors="coerce")
    return orders


def build_clean_fact(raw: pd.DataFrame, salt: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    duration = (raw["chargeEnd"] - raw["chargeBegin"]).dt.total_seconds() / 60
    invalid_key = raw["orderNum"].isna() | raw["orderNum"].duplicated(keep=False)
    invalid_duration = raw["chargeBegin"].isna() | raw["chargeEnd"].isna() | duration.le(0) | raw["chargeTimeMinute"].le(0)
    excluded_mask = invalid_key | invalid_duration

    excluded = raw.loc[excluded_mask, ["orderNum", "chargeBegin", "chargeEnd", "chargingPower", "endReason"]].copy()
    excluded["exclusion_reason"] = [
        ";".join(filter(None, [
            "missing_or_duplicate_order_key" if invalid_key.loc[index] else "",
            "missing_or_nonpositive_cloud_duration" if invalid_duration.loc[index] else "",
        ]))
        for index in excluded.index
    ]

    clean = raw.loc[~excluded_mask].copy()
    clean["user_key"] = clean.get("userNum", pd.Series(index=clean.index, dtype=object)).map(
        lambda value: pseudonym(value, "user", salt)
    )
    vehicle = clean.get("carVin", pd.Series(index=clean.index, dtype=object)).combine_first(
        clean.get("carLicense", pd.Series(index=clean.index, dtype=object))
    )
    clean["vehicle_key"] = vehicle.map(lambda value: pseudonym(value, "vehicle", salt))
    clean["duration_minutes_calculated"] = ((clean["chargeEnd"] - clean["chargeBegin"]).dt.total_seconds() / 60).round(3)
    clean["is_zero_energy_session"] = clean["chargingPower"].fillna(0).le(0)
    clean["is_paid"] = clean.get("payStatus", pd.Series(index=clean.index, dtype=object)).eq("已支付")
    clean["is_soc_missing"] = clean[["beginSOC", "endSOC"]].isna().any(axis=1)
    clean["is_soc_reverse"] = clean["beginSOC"].notna() & clean["endSOC"].notna() & clean["endSOC"].lt(clean["beginSOC"])
    clean["is_native_detail_missing"] = clean[["chargeBeginNative", "chargeEndNative", "chargeTimeNative"]].isna().any(axis=1)
    clean["fee_balance_ok"] = (
        clean["chargingPay"] - clean["chargingelectricityPay"] - clean["chargingServicePay"]
    ).abs().le(0.01)

    clean = clean.drop(columns=[column for column in PRIVATE_COLUMNS if column in clean.columns])
    return clean, excluded


def build_quality_report(raw: pd.DataFrame, clean: pd.DataFrame, excluded: pd.DataFrame) -> pd.DataFrame:
    rows = [
        ("raw_rows", len(raw), "Source data rows"),
        ("unique_order_keys", raw["orderNum"].nunique(dropna=True), "orderNum must be non-null and unique"),
        ("excluded_rows", len(excluded), "Only invalid keys or non-positive cloud duration are excluded"),
        ("clean_rows", len(clean), "Analytical sessions retained after hard exclusions"),
        ("retained_zero_energy_sessions", int(clean["is_zero_energy_session"].sum()), "Operational attempts remain analyzable"),
        ("retained_unpaid_rows", int((~clean["is_paid"]).sum()), "Payment status is not a validity rule"),
        ("retained_soc_missing_rows", int(clean["is_soc_missing"].sum()), "Device-reporting quality flag"),
        ("retained_soc_reverse_rows", int(clean["is_soc_reverse"].sum()), "Device-reporting quality flag"),
        ("fee_balance_failures", int((~clean["fee_balance_ok"]).sum()), "Gross amount = electricity + service amount, tolerance 0.01"),
    ]
    return pd.DataFrame(rows, columns=["metric", "value", "business_rule"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Private source .xlsx file")
    parser.add_argument("--output-dir", type=Path, default=Path("data/private_processed"))
    parser.add_argument("--salt-file", type=Path, required=True, help="Local secret text file; keep outside Git")
    args = parser.parse_args()

    salt = args.salt_file.read_text(encoding="utf-8").strip()
    if len(salt) < 16:
        raise ValueError("The local pseudonymization salt must contain at least 16 characters")

    raw = load_orders(args.source)
    clean, excluded = build_clean_fact(raw, salt)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    clean.to_csv(args.output_dir / "clean_charging_orders.csv", index=False, encoding="utf-8-sig")
    excluded.to_csv(args.output_dir / "excluded_orders.csv", index=False, encoding="utf-8-sig")
    build_quality_report(raw, clean, excluded).to_csv(
        args.output_dir / "data_quality_report.csv", index=False, encoding="utf-8-sig"
    )
    print(f"raw_rows={len(raw)} clean_rows={len(clean)} excluded_rows={len(excluded)}")
    print(f"private_output={args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
