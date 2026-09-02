-- Business question: When does charging demand occur, and how do weekdays differ from weekends?
-- query: hourly_orders
SELECT
    CAST(strftime('%H', start_time) AS INTEGER) AS hour,
    COUNT(*) AS order_count,
    ROUND(SUM(total_amount), 2) AS revenue
FROM charging_orders
GROUP BY hour
ORDER BY hour;

-- query: weekday_weekend
SELECT
    CASE WHEN CAST(strftime('%w', start_time) AS INTEGER) IN (0, 6)
         THEN 'weekend' ELSE 'weekday' END AS day_type,
    COUNT(*) AS order_count,
    ROUND(SUM(total_amount), 2) AS revenue,
    ROUND(AVG(total_amount), 2) AS avg_order_value
FROM charging_orders
GROUP BY day_type
ORDER BY day_type;
