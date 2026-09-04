# Real-order cleaning rules

## Grain and primary key

One source row represents one charging order. In the reviewed workbook, all 52,765 `orderNum` values were populated and unique, so `orderNum` is the business primary key for quality checks. `businessNum` is treated as an internal transaction identifier and is not published.

## Canonical time

`chargeBegin` and `chargeEnd` are the canonical cloud-platform timestamps. Native terminal fields remain auxiliary diagnostics because 221 source rows lacked native details and one native timestamp was implausibly old while its cloud timestamps were valid.

## Hard exclusions

A row is excluded from the trusted charging fact only when:

1. `orderNum` is missing or duplicated; or
2. a canonical timestamp is missing; or
3. `chargeEnd <= chargeBegin`; or
4. reported `chargeTimeMinute <= 0`.

The reviewed file had 222 excluded rows. All had zero duration and zero energy; 207 ended because the charger start response timed out. Exclusions are written to a private audit file so nothing is silently discarded.

## Retained quality and operational flags

- Zero-energy orders with positive duration are retained as operational attempts. The reviewed file contained 1,959 such rows, commonly associated with communication, insulation or connection failures.
- Every `endReason`, including abnormal stops, is retained because it is an analysis dimension.
- Unpaid orders are retained and flagged. Payment state is not evidence that a charging record is invalid.
- Missing or decreasing SOC is retained and flagged as device-reporting quality.
- Missing native terminal detail is retained when canonical cloud timestamps are valid.
- Fee conservation uses a tolerance of 0.01: gross amount must equal electricity amount plus service amount.

## Privacy controls

Direct identifiers are removed from the analytical export: user number, company name, card number, license plate, VIN, internal vehicle label, department and internal business number. Repeat-user and repeat-vehicle analysis uses salted SHA-256 keys. The salt is required at runtime and must remain outside Git.

Pseudonymized row-level data is still treated as private business data. The full 52,543-row clean fact table is not published. GitHub receives only aggregate summaries and a fully synthetic sample.
