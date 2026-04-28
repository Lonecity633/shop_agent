-- 首页分类/收藏/购物车能力（v5）

CREATE TABLE IF NOT EXISTS categories (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(80) NOT NULL,
  sort_order INT NOT NULL DEFAULT 100,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_categories_name (name),
  INDEX idx_categories_sort_order (sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE products
  ADD COLUMN category_id INT NULL AFTER seller_id,
  ADD INDEX idx_products_category_id (category_id),
  ADD CONSTRAINT fk_products_category_id FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS favorites (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  product_id INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_favorites_user_product (user_id, product_id),
  INDEX idx_favorites_user_id (user_id),
  INDEX idx_favorites_product_id (product_id),
  CONSTRAINT fk_favorites_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_favorites_product_id FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cart_items (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  selected TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_cart_items_user_product (user_id, product_id),
  INDEX idx_cart_items_user_id (user_id),
  INDEX idx_cart_items_product_id (product_id),
  CONSTRAINT fk_cart_items_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_cart_items_product_id FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO categories(name, sort_order, is_active)
SELECT '数码家电', 10, 1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = '数码家电');
INSERT INTO categories(name, sort_order, is_active)
SELECT '服饰箱包', 20, 1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = '服饰箱包');
INSERT INTO categories(name, sort_order, is_active)
SELECT '食品生鲜', 30, 1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = '食品生鲜');
INSERT INTO categories(name, sort_order, is_active)
SELECT '家居日用', 40, 1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = '家居日用');
