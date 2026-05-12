-- 沙箱风格支付流水
USE shop_db;

CREATE TABLE IF NOT EXISTS payment_transactions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  payment_no VARCHAR(40) NOT NULL,
  order_id INT NOT NULL,
  buyer_id INT NOT NULL,
  channel VARCHAR(32) NOT NULL DEFAULT 'mock_alipay',
  amount DECIMAL(10, 2) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  provider_trade_no VARCHAR(64) NOT NULL DEFAULT '',
  failure_reason VARCHAR(2000) NOT NULL DEFAULT '',
  callback_payload LONGTEXT NOT NULL,
  paid_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_payment_transactions_payment_no (payment_no),
  KEY idx_payment_transactions_order_status (order_id, status),
  KEY idx_payment_transactions_buyer_created (buyer_id, created_at),
  CONSTRAINT fk_payment_transactions_order
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_payment_transactions_buyer
    FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
