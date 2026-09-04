-- name: overview
SELECT
    COUNT(DISTINCT orderNum) AS total_orders,
    ROUND(SUM(chargingPower), 3) AS total_charging_kwh,
    ROUND(SUM(chargingPay), 2) AS total_amount_due,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS total_amount_paid,
    ROUND(SUM(chargingelectricityPay), 2) AS total_electricity_fee,
    ROUND(SUM(chargingServicePay), 2) AS total_service_fee,
    ROUND(SUM(chargingDiscount), 2) AS total_discount,
    ROUND(AVG(chargingPay), 2) AS avg_order_amount,
    ROUND(AVG(chargingPower), 3) AS avg_charging_kwh,
    ROUND(AVG(duration_minutes_calculated), 2) AS avg_charging_duration,
    COUNT(DISTINCT CASE WHEN user_key IS NOT NULL THEN user_key END) AS active_users,
    COUNT(DISTINCT stationName || CHAR(31) || CAST(plugNum AS TEXT)) AS active_plugs
FROM clean_charging_orders;
