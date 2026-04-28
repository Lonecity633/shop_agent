-- MySQL migration for order workflow v2 (shipping/receiving/comment/audit logs)

ALTER TABLE orders
  MODIFY COLUMN status ENUM('created','shipped','received','completed','cancelled') NOT NULL DEFAULT 'created';

ALTER TABLE orders
  ADD COLUMN tracking_no VARCHAR(64) NOT NULL DEFAULT '' AFTER total_price,
  ADD COLUMN logistics_company VARCHAR(120) NOT NULL DEFAULT '' AFTER tracking_no,
  ADD COLUMN shipped_at DATETIME NULL AFTER logistics_company,
  ADD COLUMN received_at DATETIME NULL AFTER shipped_at,
  ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER received_at,
  ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

CREATE TABLE IF NOT EXISTS order_status_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  from_status VARCHAR(32) NOT NULL,
  to_status VARCHAR(32) NOT NULL,
  actor_id INT NOT NULL,
  actor_role VARCHAR(32) NOT NULL,
  reason TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_order_status_logs_order_id (order_id),
  INDEX idx_order_status_logs_actor_id (actor_id),
  CONSTRAINT fk_order_status_logs_order_id FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_order_status_logs_actor_id FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS comments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  product_id INT NOT NULL,
  user_id INT NOT NULL,
  rating INT NOT NULL,
  content TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_comment_order_id (order_id),
  INDEX idx_comments_product_id (product_id),
  INDEX idx_comments_user_id (user_id),
  CONSTRAINT fk_comments_order_id FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_comments_product_id FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  CONSTRAINT fk_comments_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
