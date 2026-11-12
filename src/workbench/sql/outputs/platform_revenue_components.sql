-- October platform revenue per schedule component: days / 365, rounded once per month, half up.
SELECT * FROM platform_revenue_components ORDER BY customer_name, component_start
