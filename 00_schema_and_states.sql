SELECT table_name,column_name,data_type
FROM `bussiness-case-tyc.bussiness_case_ecommerce.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name IN ('orders','order_items','users','products','events')
ORDER BY table_name,ordinal_position;

SELECT status, COUNT(*) AS filas, COUNT(DISTINCT order_id) AS ordenes_unicas,
COUNT(DISTINCT user_id) AS clientes, MIN(created_at) AS primera_fecha,
MAX(created_at) AS ultima_fecha, COUNTIF(order_id IS NULL) AS ids_orden_nulos,
COUNTIF(user_id IS NULL) AS ids_cliente_nulos, COUNTIF(created_at IS NULL) AS fechas_nulas
FROM `bussiness-case-tyc.bussiness_case_ecommerce.orders`
GROUP BY status ORDER BY filas DESC;
