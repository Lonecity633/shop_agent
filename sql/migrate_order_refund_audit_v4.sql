-- 订单/退款闭环 + 审计能力（Phase 1）
USE shop_db;

-- 1) 订单库存回补幂等标记
ALTER TABLE orders
  ADD COLUMN inventory_reverted TINYINT(1) NOT NULL DEFAULT 0 AFTER close_reason;

-- 2) 退款执行态字段
ALTER TABLE refund_tickets
  ADD COLUMN fail_reason VARCHAR(2000) NOT NULL DEFAULT '' AFTER admin_note,
  ADD COLUMN processed_at DATETIME NULL AFTER fail_reason;

-- 3) 统一操作审计表
CREATE TABLE IF NOT EXISTS operation_audits (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  entity_type VARCHAR(32) NOT NULL,
  entity_id BIGINT NOT NULL,
  action VARCHAR(64) NOT NULL,
  actor_id BIGINT NOT NULL,
  actor_role VARCHAR(32) NOT NULL,
  before_state LONGTEXT NOT NULL,
  after_state LONGTEXT NOT NULL,
  reason LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4) 索引
CREATE INDEX idx_orders_status_pay_created ON orders(status, pay_status, created_at);
CREATE INDEX idx_refund_tickets_status_created ON refund_tickets(status, created_at);
CREATE INDEX idx_operation_audits_entity_time ON operation_audits(entity_type, entity_id, created_at);
