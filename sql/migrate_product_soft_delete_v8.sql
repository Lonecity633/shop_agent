-- 商品逻辑删除（v8）
-- 目标：
-- 1) products 增加 is_deleted 字段
-- 2) 历史数据默认未删除
-- 3) 增加索引以支撑查询过滤

SET @col_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'products'
    AND COLUMN_NAME = 'is_deleted'
);

SET @sql_add_col := IF(
  @col_exists = 0,
  'ALTER TABLE products ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0',
  'SELECT 1'
);
PREPARE stmt_add_col FROM @sql_add_col;
EXECUTE stmt_add_col;
DEALLOCATE PREPARE stmt_add_col;

SET @sql_fill_null := 'UPDATE products SET is_deleted = 0 WHERE is_deleted IS NULL';
PREPARE stmt_fill_null FROM @sql_fill_null;
EXECUTE stmt_fill_null;
DEALLOCATE PREPARE stmt_fill_null;

SET @idx_exists := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'products'
    AND INDEX_NAME = 'idx_products_is_deleted'
);

SET @sql_add_idx := IF(
  @idx_exists = 0,
  'ALTER TABLE products ADD INDEX idx_products_is_deleted (is_deleted)',
  'SELECT 1'
);
PREPARE stmt_add_idx FROM @sql_add_idx;
EXECUTE stmt_add_idx;
DEALLOCATE PREPARE stmt_add_idx;
