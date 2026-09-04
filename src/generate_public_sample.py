"""Generate a deterministic synthetic sample matching the safe clean schema."""

from __future__ import annotations

from pathlib import Path
import random

import pandas as pd


def main() -> None:
    random.seed(20260904)
    rows = []
    base = pd.Timestamp("2025-01-01 06:00:00")
    normal_reasons = ["user_stop", "vehicle_target_reached", "platform_stop"]
    exception_reasons = ["communication_timeout", "connector_interrupted"]
    for index in range(100):
        start = base + pd.Timedelta(hours=index * 3 + index % 5)
        duration = random.randint(18, 95)
        zero_energy = index in {17, 43, 79}
        energy = 0.0 if zero_energy else round(random.uniform(8, 72), 2)
        service = round(energy * 0.35, 2)
        electricity = round(energy * random.choice([0.65, 0.82, 1.05]), 2)
        rows.append({
            "sample_order_id": f"SAMPLE-{index + 1:03d}",
            "station_code": f"S{index % 5 + 1:03d}",
            "anonymous_user_segment": ["occasional", "regular", "frequent"][index % 3],
            "charge_begin": start,
            "charge_end": start + pd.Timedelta(minutes=duration),
            "charge_time_minutes": duration,
            "charging_kwh": energy,
            "electricity_amount": electricity,
            "service_amount": service,
            "gross_amount": round(electricity + service, 2),
            "pay_status": "paid" if index % 19 else "unpaid",
            "end_reason_category": random.choice(exception_reasons if zero_energy else normal_reasons),
            "is_zero_energy_session": zero_energy,
            "data_origin": "fully_synthetic",
        })
    target = Path(__file__).resolve().parents[1] / "data" / "clean_sample.csv"
    pd.DataFrame(rows).to_csv(target, index=False, encoding="utf-8-sig")
    print(f"created={target} rows={len(rows)}")


if __name__ == "__main__":
    main()
