-- BigQuery Standard SQL. Una fila por cliente. No modifica el origen.
-- Target principal: nueva ORDEN CREADA, independientemente de su estado posterior.
-- Los estados finales no están disponibles históricamente y no filtran features.
-- Corte exclusivo 2025-02-14 UTC: se omite el último día parcial del snapshot.
DECLARE cutoff_ts TIMESTAMP DEFAULT TIMESTAMP('2025-02-14 00:00:00+00');

WITH orders_asof AS (
  SELECT order_id,user_id,created_at,status,num_of_item
  FROM `bussiness-case-tyc.bussiness_case_ecommerce.orders`
  WHERE created_at < cutoff_ts AND user_id IS NOT NULL AND order_id IS NOT NULL
), first_order AS (
  SELECT * FROM orders_asof
  QUALIFY ROW_NUMBER() OVER(PARTITION BY user_id ORDER BY created_at,order_id)=1
), labels AS (
  SELECT f.user_id,
    MIN(IF(o.created_at>f.created_at,o.created_at,NULL)) AS next_order_at,
    COUNTIF(o.created_at>f.created_at AND o.created_at<=TIMESTAMP_ADD(f.created_at, INTERVAL 60 DAY))>0 AS repeat_60,
    COUNTIF(o.created_at>f.created_at AND o.created_at<=TIMESTAMP_ADD(f.created_at, INTERVAL 60 DAY) AND o.status!='Cancelled')>0 AS repeat_60_non_cancelled
  FROM first_order f LEFT JOIN orders_asof o USING(user_id)
  GROUP BY f.user_id
), basket AS (
  -- Agregar antes de unir evita multiplicar clientes por ítems.
  SELECT f.user_id, COUNT(i.id) AS observed_items,
    SUM(i.sale_price) AS basket_value,
    COUNT(DISTINCT i.product_id) AS unique_products,
    COUNT(DISTINCT p.category) AS unique_categories,
    ARRAY_AGG(p.category IGNORE NULLS ORDER BY i.sale_price DESC,i.id LIMIT 1)[SAFE_OFFSET(0)] AS main_category
  FROM first_order f
  LEFT JOIN `bussiness-case-tyc.bussiness_case_ecommerce.order_items` i
    ON f.order_id=i.order_id AND f.user_id=i.user_id AND i.created_at<=f.created_at
  LEFT JOIN `bussiness-case-tyc.bussiness_case_ecommerce.products` p ON i.product_id=p.id
  GROUP BY f.user_id
), activity AS (
  SELECT f.user_id, COUNT(e.id) AS events_30d,
    COUNT(DISTINCT e.session_id) AS sessions_30d,
    COUNTIF(e.event_type='product') AS product_views_30d,
    ARRAY_AGG(e.traffic_source IGNORE NULLS ORDER BY e.created_at DESC,e.id DESC LIMIT 1)[SAFE_OFFSET(0)] AS last_traffic_source,
    ARRAY_AGG(e.browser IGNORE NULLS ORDER BY e.created_at DESC,e.id DESC LIMIT 1)[SAFE_OFFSET(0)] AS last_browser
  FROM first_order f
  LEFT JOIN `bussiness-case-tyc.bussiness_case_ecommerce.events` e
    ON f.user_id=e.user_id AND e.created_at<=f.created_at
    AND e.created_at>=TIMESTAMP_SUB(f.created_at, INTERVAL 30 DAY)
    AND e.created_at<cutoff_ts
  GROUP BY f.user_id
)
SELECT f.user_id, f.order_id AS first_order_id, f.created_at AS first_order_at,
  cutoff_ts AS cutoff_ts,
  TIMESTAMP_ADD(f.created_at,INTERVAL 60 DAY)<cutoff_ts AS is_mature,
  IF(TIMESTAMP_ADD(f.created_at,INTERVAL 60 DAY)<cutoff_ts,CAST(l.repeat_60 AS INT64),NULL) AS target,
  IF(TIMESTAMP_ADD(f.created_at,INTERVAL 60 DAY)<cutoff_ts,CAST(l.repeat_60_non_cancelled AS INT64),NULL) AS target_non_cancelled,
  TIMESTAMP_DIFF(l.next_order_at,f.created_at,SECOND)/86400.0 AS days_to_next_order,
  f.num_of_item AS declared_items,
  b.observed_items,b.basket_value,b.unique_products,b.unique_categories,b.main_category,
  a.events_30d,a.sessions_30d,a.product_views_30d,a.last_traffic_source,a.last_browser,
  EXTRACT(DAYOFWEEK FROM f.created_at) AS purchase_dayofweek,
  EXTRACT(HOUR FROM f.created_at) AS purchase_hour,
  EXTRACT(MONTH FROM f.created_at) AS purchase_month
FROM first_order f
LEFT JOIN labels l USING(user_id)
LEFT JOIN basket b USING(user_id)
LEFT JOIN activity a USING(user_id);
