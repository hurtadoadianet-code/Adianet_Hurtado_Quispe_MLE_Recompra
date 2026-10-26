-- Solo lectura. Corte exclusivo: primer día posterior al último día completo.
WITH o AS (SELECT * FROM `bussiness-case-tyc.bussiness_case_ecommerce.orders`),
i AS (SELECT * FROM `bussiness-case-tyc.bussiness_case_ecommerce.order_items`),
u AS (SELECT * FROM `bussiness-case-tyc.bussiness_case_ecommerce.users`),
p AS (SELECT * FROM `bussiness-case-tyc.bussiness_case_ecommerce.products`)
SELECT 'orders_rows' AS control, COUNT(*) AS valor FROM o
UNION ALL SELECT 'orders_duplicate_ids', COUNT(*)-COUNT(DISTINCT order_id) FROM o
UNION ALL SELECT 'orders_null_keys_dates', COUNTIF(order_id IS NULL OR user_id IS NULL OR created_at IS NULL) FROM o
UNION ALL SELECT 'users_duplicate_ids', COUNT(*)-COUNT(DISTINCT id) FROM u
UNION ALL SELECT 'products_duplicate_ids', COUNT(*)-COUNT(DISTINCT id) FROM p
UNION ALL SELECT 'items_duplicate_ids', COUNT(*)-COUNT(DISTINCT id) FROM i
UNION ALL SELECT 'orders_without_user', COUNT(*) FROM o LEFT JOIN u ON o.user_id=u.id WHERE u.id IS NULL
UNION ALL SELECT 'items_without_order', COUNT(*) FROM i LEFT JOIN o USING(order_id) WHERE o.order_id IS NULL
UNION ALL SELECT 'items_without_product', COUNT(*) FROM i LEFT JOIN p ON i.product_id=p.id WHERE p.id IS NULL
UNION ALL SELECT 'items_user_mismatch', COUNT(*) FROM i JOIN o USING(order_id) WHERE i.user_id!=o.user_id
UNION ALL SELECT 'items_after_order_timestamp', COUNT(*) FROM i JOIN o USING(order_id) WHERE i.created_at>o.created_at
UNION ALL SELECT 'items_null_price', COUNTIF(sale_price IS NULL) FROM i
UNION ALL SELECT 'items_negative_price', COUNTIF(sale_price<0) FROM i
UNION ALL SELECT 'orders_without_items', COUNT(*) FROM o LEFT JOIN (SELECT DISTINCT order_id FROM i) z USING(order_id) WHERE z.order_id IS NULL
UNION ALL SELECT 'orders_before_user_registration', COUNT(*) FROM o JOIN u ON o.user_id=u.id WHERE o.created_at<u.created_at;
