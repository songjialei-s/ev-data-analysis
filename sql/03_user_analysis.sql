-- Business question: Which users drive orders and revenue, and how frequently do they charge?
-- query: user_ranking
SELECT
    user_id,
    COUNT(*) AS order_count,
    ROUND(SUM(total_amount), 2) AS total_revenue,
    ROUND(SUM(charging_kwh), 2) AS total_charging_kwh,
    ROUND(AVG(total_amount), 2) AS avg_order_value
FROM charging_orders
GROUP BY user_id
ORDER BY total_revenue DESC, order_count DESC;

-- query: user_frequency_segments
WITH user_metrics AS (
    SELECT user_id, COUNT(*) AS order_count, SUM(total_amount) AS revenue
    FROM charging_orders
    GROUP BY user_id
)
SELECT
    CASE
        WHEN order_count >= 12 THEN 'high_frequency'
        WHEN order_count >= 6 THEN 'medium_frequency'
        ELSE 'low_frequency'
    END AS frequency_segment,
    COUNT(*) AS user_count,
    SUM(order_count) AS order_count,
    ROUND(SUM(revenue), 2) AS revenue
FROM user_metrics
GROUP BY frequency_segment
ORDER BY CASE frequency_segment
    WHEN 'high_frequency' THEN 1
    WHEN 'medium_frequency' THEN 2
    ELSE 3 END;
