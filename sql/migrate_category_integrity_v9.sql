-- 分类完整性与删除迁移治理（v9）
-- 目标：
-- 1) 保证系统保底分类“其他”存在且启用
-- 2) 修复历史失联商品分类（NULL 或悬挂外键）到“其他”
-- 3) 收紧 products.category_id 为 NOT NULL + ON DELETE RESTRICT

START TRANSACTION;

INSERT INTO categories(name, sort_order, is_active)
SELECT '其他', 9999, 1
FROM DUAL
WHERE NOT EXISTS (
  SELECT 1 FROM categories WHERE name = '其他'
);

UPDATE categories
SET is_active = 1
WHERE name = '其他' AND is_active = 0;

UPDATE products p
JOIN categories fallback ON fallback.name = '其他'
LEFT JOIN categories c ON c.id = p.category_id
SET p.category_id = fallback.id
WHERE p.category_id IS NULL OR c.id IS NULL;

COMMIT;

SET @fk_exists := (
  SELECT COUNT(*)
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND TABLE_NAME = 'products'
    AND CONSTRAINT_NAME = 'fk_products_category_id'
    AND CONSTRAINT_TYPE = 'FOREIGN KEY'
);
SET @sql_drop_fk := IF(@fk_exists > 0, 'ALTER TABLE products DROP FOREIGN KEY fk_products_category_id', 'SELECT 1');
PREPARE stmt_drop_fk FROM @sql_drop_fk;
EXECUTE stmt_drop_fk;
DEALLOCATE PREPARE stmt_drop_fk;

SET @idx_exists := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'products'
    AND INDEX_NAME = 'idx_products_category_id'
);
SET @sql_add_idx := IF(@idx_exists = 0, 'ALTER TABLE products ADD INDEX idx_products_category_id (category_id)', 'SELECT 1');
PREPARE stmt_add_idx FROM @sql_add_idx;
EXECUTE stmt_add_idx;
DEALLOCATE PREPARE stmt_add_idx;

SET @col_nullable := (
  SELECT IS_NULLABLE
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'products'
    AND COLUMN_NAME = 'category_id'
  LIMIT 1
);
SET @sql_set_not_null := IF(@col_nullable = 'YES', 'ALTER TABLE products MODIFY COLUMN category_id INT NOT NULL', 'SELECT 1');
PREPARE stmt_set_not_null FROM @sql_set_not_null;
EXECUTE stmt_set_not_null;
DEALLOCATE PREPARE stmt_set_not_null;

SET @fk_exists_after := (
  SELECT COUNT(*)
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND TABLE_NAME = 'products'
    AND CONSTRAINT_NAME = 'fk_products_category_id'
    AND CONSTRAINT_TYPE = 'FOREIGN KEY'
);
SET @sql_add_fk := IF(
  @fk_exists_after = 0,
  'ALTER TABLE products ADD CONSTRAINT fk_products_category_id FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT',
  'SELECT 1'
);
PREPARE stmt_add_fk FROM @sql_add_fk;
EXECUTE stmt_add_fk;
DEALLOCATE PREPARE stmt_add_fk;
