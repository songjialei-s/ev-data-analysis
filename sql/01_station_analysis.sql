-- Business question: Which stations lead on demand, revenue, charging volume, and per-pile efficiency?
-- query: station_performance
WITH coverage AS (
    SELECT MAX(1, CAST(julianday(MAX(date(start_time))) - julianday(MIN(date(start_time))) + 1 AS INTEGER)) AS days
    FROM charging_orders
), station_metrics AS (
    SELECT
        s.station_id,
        s.station_name,
        s.pile_count,
        COUNT(o.order_id) AS order_count,
        ROUND(SUM(o.charging_kwh), 2) AS charging_kwh,
        ROUND(SUM(o.total_amount), 2) AS revenue
    FROM stations s
    LEFT JOIN charging_orders o ON s.station_id = o.station_id
    GROUP BY s.station_id, s.station_name, s.pile_count
)
SELECT
    station_id,
    station_name,
    pile_count,
    order_count,
    charging_kwh,
    revenue,
    ROUND(order_count * 1.0 / NULLIF(pile_count * coverage.days, 0), 4) AS orders_per_pile,
    ROUND(revenue / NULLIF(pile_count, 0), 2) AS revenue_per_pile
FROM station_metrics
CROSS JOIN coverage
ORDER BY order_count DESC, revenue DESC;
