USE shop_db;

SET @has_order_no := (
  SELECT COUNT(1)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'orders'
    AND column_name = 'order_no'
);
SET @sql_add_col := IF(@has_order_no = 0,
  'ALTER TABLE orders ADD COLUMN order_no VARCHAR(32) NULL AFTER id',
  'SELECT 1'
);
PREPARE stmt_add_col FROM @sql_add_col;
EXECUTE stmt_add_col;
DEALLOCATE PREPARE stmt_add_col;

UPDATE orders
SET order_no = CONCAT('SO', DATE_FORMAT(COALESCE(created_at, NOW()), '%Y%m%d%H%i%S'), LPAD(id, 8, '0'))
WHERE order_no IS NULL OR order_no = '';

ALTER TABLE orders
  MODIFY COLUMN order_no VARCHAR(32) NOT NULL;

SET @has_uq_order_no := (
  SELECT COUNT(1)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'orders'
    AND index_name = 'uq_orders_order_no'
);
SET @sql_add_uq := IF(@has_uq_order_no = 0,
  'ALTER TABLE orders ADD UNIQUE KEY uq_orders_order_no (order_no)',
  'SELECT 1'
);
PREPARE stmt_add_uq FROM @sql_add_uq;
EXECUTE stmt_add_uq;
DEALLOCATE PREPARE stmt_add_uq;
