-- name: station_analysis
SELECT
    stationName,
    COUNT(DISTINCT orderNum) AS order_count,
    ROUND(SUM(chargingPower), 3) AS charging_kwh,
    ROUND(SUM(chargingPay), 2) AS amount_due,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS amount_paid,
    ROUND(SUM(chargingelectricityPay), 2) AS electricity_fee,
    ROUND(SUM(chargingServicePay), 2) AS service_fee,
    ROUND(AVG(chargingPay), 2) AS avg_order_amount,
    ROUND(AVG(chargingPower), 3) AS avg_charging_kwh,
    ROUND(AVG(duration_minutes_calculated), 2) AS avg_duration,
    COUNT(DISTINCT stationName || CHAR(31) || CAST(plugNum AS TEXT)) AS active_plug_count,
    ROUND(1.0 * COUNT(DISTINCT orderNum) /
          COUNT(DISTINCT stationName || CHAR(31) || CAST(plugNum AS TEXT)), 3) AS orders_per_active_plug,
    ROUND(SUM(chargingPower) /
          COUNT(DISTINCT stationName || CHAR(31) || CAST(plugNum AS TEXT)), 3) AS kwh_per_active_plug,
    ROUND(SUM(chargingPay) /
          COUNT(DISTINCT stationName || CHAR(31) || CAST(plugNum AS TEXT)), 2) AS revenue_per_active_plug
FROM clean_charging_orders
GROUP BY stationName
ORDER BY order_count DESC, stationName;
