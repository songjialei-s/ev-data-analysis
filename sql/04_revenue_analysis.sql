-- Business question: How is revenue composed, and which station revenue patterns require attention?
-- query: revenue_composition
SELECT
    ROUND(SUM(charging_fee), 2) AS charging_fee_revenue,
    ROUND(SUM(service_fee), 2) AS service_fee_revenue,
    ROUND(SUM(total_amount), 2) AS total_revenue,
    ROUND(SUM(service_fee) / NULLIF(SUM(total_amount), 0), 4) AS service_fee_share,
    ROUND(AVG(total_amount), 2) AS avg_order_value,
    ROUND(SUM(total_amount) / NULLIF(SUM(charging_kwh), 0), 4) AS revenue_per_kwh
FROM charging_orders;

-- query: station_revenue
WITH station_metrics AS (
    SELECT
        s.station_id,
        s.station_name,
        s.pile_count,
        COUNT(o.order_id) AS order_count,
        SUM(o.total_amount) AS revenue,
        AVG(o.total_amount) AS avg_order_value,
        SUM(o.total_amount) / NULLIF(SUM(o.charging_kwh), 0) AS revenue_per_kwh
    FROM stations s
    LEFT JOIN charging_orders o ON s.station_id = o.station_id
    GROUP BY s.station_id, s.station_name, s.pile_count
), benchmarks AS (
    SELECT AVG(order_count) AS avg_orders, AVG(revenue) AS avg_revenue,
           AVG(avg_order_value) AS avg_order_value
    FROM station_metrics
)
SELECT
    station_id,
    station_name,
    order_count,
    ROUND(revenue, 2) AS revenue,
    ROUND(revenue / NULLIF(pile_count, 0), 2) AS revenue_per_pile,
    ROUND(station_metrics.avg_order_value, 2) AS avg_order_value,
    ROUND(station_metrics.revenue_per_kwh, 4) AS revenue_per_kwh,
    CASE
        WHEN order_count >= avg_orders AND revenue >= avg_revenue THEN 'high_orders_high_revenue'
        WHEN order_count >= avg_orders AND station_metrics.avg_order_value < benchmarks.avg_order_value THEN 'high_orders_low_avg_value'
        WHEN order_count < avg_orders AND station_metrics.avg_order_value >= benchmarks.avg_order_value THEN 'low_orders_high_avg_value'
        ELSE 'low_orders_low_revenue'
    END AS revenue_pattern
FROM station_metrics
CROSS JOIN benchmarks
ORDER BY revenue DESC;
