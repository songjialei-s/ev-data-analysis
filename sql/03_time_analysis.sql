-- name: monthly_analysis
SELECT
    charge_month AS month,
    COUNT(DISTINCT orderNum) AS order_count,
    ROUND(SUM(chargingPower), 3) AS charging_kwh,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS amount_paid
FROM clean_charging_orders
GROUP BY charge_month
ORDER BY charge_month;

-- name: daily_analysis
SELECT
    charge_date,
    COUNT(DISTINCT orderNum) AS order_count,
    ROUND(SUM(chargingPower), 3) AS charging_kwh,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS amount_paid
FROM clean_charging_orders
GROUP BY charge_date
ORDER BY charge_date;

-- name: weekday_analysis
SELECT
    weekday_number,
    weekday_name,
    COUNT(DISTINCT orderNum) AS order_count,
    ROUND(SUM(chargingPower), 3) AS charging_kwh,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS amount_paid
FROM clean_charging_orders
GROUP BY weekday_number, weekday_name
ORDER BY weekday_number;

-- name: day_type_analysis
SELECT
    day_type,
    COUNT(DISTINCT orderNum) AS order_count,
    ROUND(SUM(chargingPower), 3) AS charging_kwh,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS amount_paid
FROM clean_charging_orders
GROUP BY day_type
ORDER BY day_type;

-- name: hourly_analysis
SELECT
    charge_hour AS hour,
    COUNT(DISTINCT orderNum) AS order_count,
    ROUND(SUM(chargingPower), 3) AS charging_kwh,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS amount_paid
FROM clean_charging_orders
GROUP BY charge_hour
ORDER BY charge_hour;

-- name: time_of_use_summary
SELECT 'peak' AS period,
       ROUND(SUM(peakElectricityPower), 3) AS charging_kwh,
       ROUND(SUM(peakElectricityBill), 2) AS electricity_fee,
       ROUND(SUM(peakServiceBill), 2) AS service_fee
FROM clean_charging_orders
UNION ALL
SELECT 'superpeak', ROUND(SUM(superpeakElectricityPower), 3),
       ROUND(SUM(superpeakElectricityBill), 2), ROUND(SUM(superpeakServiceBill), 2)
FROM clean_charging_orders
UNION ALL
SELECT 'valley', ROUND(SUM(valleyElectricityPower), 3),
       ROUND(SUM(valleyElectricityBill), 2), ROUND(SUM(valleyServiceBill), 2)
FROM clean_charging_orders
UNION ALL
SELECT 'normal', ROUND(SUM(normalElectricityPower), 3),
       ROUND(SUM(normalElectricityBill), 2), ROUND(SUM(normalServiceBill), 2)
FROM clean_charging_orders
UNION ALL
SELECT 'peak2', ROUND(SUM(peak2ElectricityPower), 3),
       ROUND(SUM(peak2ElectricityBill), 2), ROUND(SUM(peak2ServiceBill), 2)
FROM clean_charging_orders
UNION ALL
SELECT 'deepvalley', ROUND(SUM(deepvalleyElectricityPower), 3),
       ROUND(SUM(deepvalleyElectricityBill), 2), ROUND(SUM(deepvalleyServiceBill), 2)
FROM clean_charging_orders;
