-- name: end_reason_analysis
SELECT
    endReason,
    end_reason_category,
    COUNT(DISTINCT orderNum) AS order_count,
    ROUND(1.0 * COUNT(DISTINCT orderNum) /
          SUM(COUNT(DISTINCT orderNum)) OVER (), 6) AS order_share
FROM clean_charging_orders
GROUP BY endReason, end_reason_category
ORDER BY order_count DESC, endReason;

-- name: end_reason_station
SELECT
    stationName,
    endReason,
    end_reason_category,
    COUNT(DISTINCT orderNum) AS order_count
FROM clean_charging_orders
GROUP BY stationName, endReason, end_reason_category
ORDER BY order_count DESC, stationName, endReason;

-- name: end_reason_monthly
SELECT
    charge_month AS month,
    endReason,
    end_reason_category,
    COUNT(DISTINCT orderNum) AS order_count
FROM clean_charging_orders
GROUP BY charge_month, endReason, end_reason_category
ORDER BY month, order_count DESC, endReason;
