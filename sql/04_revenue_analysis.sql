-- name: revenue_analysis
SELECT
    'overall' AS scope,
    'ALL' AS dimension_value,
    ROUND(SUM(chargingPay), 2) AS amount_due,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS amount_paid,
    ROUND(SUM(chargingelectricityPay), 2) AS electricity_fee,
    ROUND(SUM(chargingServicePay), 2) AS service_fee,
    ROUND(SUM(chargingDiscount), 2) AS discount,
    ROUND(SUM(chargingServicePay) / NULLIF(SUM(chargingPay), 0), 6) AS service_fee_share,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END) /
          NULLIF(SUM(CASE WHEN chargingPower > 0 THEN chargingPower END), 0), 4) AS paid_amount_per_kwh,
    ROUND(AVG(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS avg_paid_order_amount
FROM clean_charging_orders;

-- name: revenue_monthly
SELECT
    charge_month AS month,
    ROUND(SUM(chargingPay), 2) AS amount_due,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS amount_paid,
    ROUND(SUM(chargingelectricityPay), 2) AS electricity_fee,
    ROUND(SUM(chargingServicePay), 2) AS service_fee,
    ROUND(SUM(chargingDiscount), 2) AS discount,
    ROUND(SUM(chargingServicePay) / NULLIF(SUM(chargingPay), 0), 6) AS service_fee_share,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END) /
          NULLIF(SUM(CASE WHEN chargingPower > 0 THEN chargingPower END), 0), 4) AS paid_amount_per_kwh,
    ROUND(AVG(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS avg_paid_order_amount
FROM clean_charging_orders
GROUP BY charge_month
ORDER BY charge_month;

-- name: revenue_station
SELECT
    stationName,
    ROUND(SUM(chargingPay), 2) AS amount_due,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS amount_paid,
    ROUND(SUM(chargingelectricityPay), 2) AS electricity_fee,
    ROUND(SUM(chargingServicePay), 2) AS service_fee,
    ROUND(SUM(chargingDiscount), 2) AS discount,
    ROUND(SUM(chargingServicePay) / NULLIF(SUM(chargingPay), 0), 6) AS service_fee_share,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END) /
          NULLIF(SUM(CASE WHEN chargingPower > 0 THEN chargingPower END), 0), 4) AS paid_amount_per_kwh,
    ROUND(AVG(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS avg_paid_order_amount
FROM clean_charging_orders
GROUP BY stationName
ORDER BY amount_paid DESC, stationName;
