-- name: sql_validation
SELECT 'row_count' AS check_name, COUNT(*) AS check_value, 'count' AS unit
FROM clean_charging_orders
UNION ALL
SELECT 'distinct_order_count', COUNT(DISTINCT orderNum), 'count'
FROM clean_charging_orders
UNION ALL
SELECT 'duplicate_order_rows', COUNT(*) - COUNT(DISTINCT orderNum), 'count'
FROM clean_charging_orders
UNION ALL
SELECT 'missing_order_key', SUM(CASE WHEN orderNum IS NULL THEN 1 ELSE 0 END), 'count'
FROM clean_charging_orders
UNION ALL
SELECT 'missing_station', SUM(CASE WHEN stationName IS NULL OR TRIM(stationName) = '' THEN 1 ELSE 0 END), 'count'
FROM clean_charging_orders
UNION ALL
SELECT 'missing_plug', SUM(CASE WHEN plugNum IS NULL OR TRIM(CAST(plugNum AS TEXT)) = '' THEN 1 ELSE 0 END), 'count'
FROM clean_charging_orders
UNION ALL
SELECT 'nonpositive_duration', SUM(CASE WHEN duration_minutes_calculated <= 0 THEN 1 ELSE 0 END), 'count'
FROM clean_charging_orders
UNION ALL
SELECT 'nonpositive_energy', SUM(CASE WHEN chargingPower <= 0 OR chargingPower IS NULL THEN 1 ELSE 0 END), 'count'
FROM clean_charging_orders
UNION ALL
SELECT 'fee_balance_failures', SUM(CASE WHEN ABS(chargingPay - chargingelectricityPay - chargingServicePay) > 0.01 THEN 1 ELSE 0 END), 'count'
FROM clean_charging_orders
WHERE chargingPay IS NOT NULL AND chargingelectricityPay IS NOT NULL AND chargingServicePay IS NOT NULL
UNION ALL
SELECT 'soc_missing', SUM(CASE WHEN beginSOC IS NULL OR endSOC IS NULL THEN 1 ELSE 0 END), 'count'
FROM clean_charging_orders
UNION ALL
SELECT 'soc_reverse', SUM(CASE WHEN beginSOC IS NOT NULL AND endSOC IS NOT NULL AND endSOC < beginSOC THEN 1 ELSE 0 END), 'count'
FROM clean_charging_orders
UNION ALL
SELECT 'unpaid_orders', SUM(CASE WHEN is_paid = 0 THEN 1 ELSE 0 END), 'count'
FROM clean_charging_orders
UNION ALL
SELECT 'unclassified_end_reason', SUM(CASE WHEN end_reason_category = '待业务确认' THEN 1 ELSE 0 END), 'count'
FROM clean_charging_orders;
