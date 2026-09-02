-- Business question: Which station metrics indicate underuse, capacity pressure, or weak revenue efficiency?
-- query: anomaly_flags
WITH coverage AS (
    SELECT MAX(1, CAST(julianday(MAX(date(start_time))) - julianday(MIN(date(start_time))) + 1 AS INTEGER)) AS days
    FROM charging_orders
), metrics AS (
    SELECT
        s.station_id,
        s.station_name,
        s.pile_count,
        COUNT(o.order_id) AS order_count,
        COUNT(o.order_id) * 1.0 / NULLIF(s.pile_count * coverage.days, 0) AS orders_per_pile,
        SUM(o.total_amount) / NULLIF(s.pile_count, 0) AS revenue_per_pile,
        SUM(o.charging_duration_hours) / NULLIF(s.pile_count * 24.0 * coverage.days, 0) AS utilization_rate
    FROM stations s
    CROSS JOIN coverage
    LEFT JOIN charging_orders o ON s.station_id = o.station_id
    GROUP BY s.station_id, s.station_name, s.pile_count, coverage.days
), benchmarks AS (
    SELECT AVG(pile_count) AS avg_piles, AVG(order_count) AS avg_orders,
           AVG(orders_per_pile) AS avg_orders_per_pile,
           AVG(revenue_per_pile) AS avg_revenue_per_pile,
           AVG(utilization_rate) AS avg_utilization
    FROM metrics
)
SELECT station_id, station_name, 'resource_underuse' AS anomaly_type,
       ROUND(orders_per_pile, 4) AS metric_value
FROM metrics CROSS JOIN benchmarks
WHERE pile_count > avg_piles AND orders_per_pile < avg_orders_per_pile
UNION ALL
SELECT station_id, station_name, 'potential_capacity_expansion', ROUND(utilization_rate, 4)
FROM metrics CROSS JOIN benchmarks
WHERE pile_count < avg_piles AND utilization_rate > avg_utilization
  AND orders_per_pile > avg_orders_per_pile
UNION ALL
SELECT station_id, station_name, 'low_revenue_efficiency', ROUND(revenue_per_pile, 2)
FROM metrics CROSS JOIN benchmarks
WHERE order_count > avg_orders AND revenue_per_pile < avg_revenue_per_pile
ORDER BY anomaly_type, station_id;
