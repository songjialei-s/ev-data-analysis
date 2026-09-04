-- name: user_analysis
SELECT
    user_key,
    COUNT(DISTINCT orderNum) AS order_count,
    ROUND(SUM(chargingPower), 3) AS charging_kwh,
    ROUND(SUM(CASE WHEN is_paid = 1 THEN chargingPayActual END), 2) AS amount_paid,
    MIN(charge_date) AS first_charge_date,
    MAX(charge_date) AS last_charge_date,
    COUNT(DISTINCT charge_date) AS active_days,
    COUNT(DISTINCT charge_month) AS active_months
FROM clean_charging_orders
WHERE user_key IS NOT NULL
GROUP BY user_key
ORDER BY order_count DESC, user_key;

-- name: user_order_distribution
WITH per_user AS (
    SELECT user_key, COUNT(DISTINCT orderNum) AS order_count
    FROM clean_charging_orders
    WHERE user_key IS NOT NULL
    GROUP BY user_key
)
SELECT
    order_count,
    COUNT(*) AS user_count,
    ROUND(1.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 6) AS user_share
FROM per_user
GROUP BY order_count
ORDER BY order_count;
