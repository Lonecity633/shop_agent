USE shop_db;

ALTER TABLE orders
  MODIFY COLUMN status VARCHAR(32) NOT NULL DEFAULT 'pending_paid';

UPDATE orders
SET status = 'pending_paid'
WHERE status = 'created';

ALTER TABLE orders
  ADD COLUMN pay_status VARCHAR(20) NOT NULL DEFAULT 'pending' AFTER status,
  ADD COLUMN pay_amount DECIMAL(10,2) NULL AFTER total_price,
  ADD COLUMN pay_channel VARCHAR(32) NOT NULL DEFAULT 'simulated' AFTER pay_amount,
  ADD COLUMN paid_at DATETIME NULL AFTER pay_channel,
  ADD COLUMN close_reason VARCHAR(255) NOT NULL DEFAULT '' AFTER paid_at,
  ADD COLUMN address_snapshot TEXT NULL AFTER close_reason;

UPDATE orders
SET pay_amount = total_price
WHERE pay_amount IS NULL;

UPDATE orders
SET pay_status = CASE
  WHEN status IN ('paid', 'shipped', 'completed') THEN 'paid'
  WHEN status IN ('cancelled', 'closed') THEN 'closed'
  ELSE 'pending'
END;

UPDATE orders
SET address_snapshot = '{}'
WHERE address_snapshot IS NULL;

ALTER TABLE orders
  MODIFY COLUMN pay_amount DECIMAL(10,2) NOT NULL,
  MODIFY COLUMN address_snapshot TEXT NOT NULL;

CREATE TABLE IF NOT EXISTS user_addresses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  receiver_name VARCHAR(60) NOT NULL,
  receiver_phone VARCHAR(30) NOT NULL,
  province VARCHAR(60) NOT NULL,
  city VARCHAR(60) NOT NULL,
  district VARCHAR(60) NOT NULL DEFAULT '',
  detail_address VARCHAR(255) NOT NULL,
  is_default TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_user_addresses_user_id (user_id),
  CONSTRAINT fk_user_addresses_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS order_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  product_id INT NOT NULL,
  product_name_snapshot VARCHAR(120) NOT NULL,
  unit_price_snapshot DECIMAL(10,2) NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  subtotal DECIMAL(10,2) NOT NULL,
  INDEX idx_order_items_order_id (order_id),
  INDEX idx_order_items_product_id (product_id),
  CONSTRAINT fk_order_items_order_id FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_order_items_product_id FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS refund_tickets (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  buyer_id INT NOT NULL,
  seller_id INT NOT NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'requested',
  amount DECIMAL(10,2) NOT NULL,
  reason TEXT NOT NULL,
  buyer_note TEXT NOT NULL,
  seller_note TEXT NOT NULL,
  admin_note TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_refund_tickets_order_id (order_id),
  INDEX idx_refund_tickets_buyer_id (buyer_id),
  INDEX idx_refund_tickets_seller_id (seller_id),
  INDEX idx_refund_tickets_status (status),
  CONSTRAINT fk_refund_tickets_order_id FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_refund_tickets_buyer_id FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_refund_tickets_seller_id FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS support_sessions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  operator_id INT NOT NULL,
  user_id INT NOT NULL,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  queried_entities TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_support_sessions_operator_id (operator_id),
  INDEX idx_support_sessions_user_id (user_id),
  CONSTRAINT fk_support_sessions_operator_id FOREIGN KEY (operator_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_support_sessions_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
