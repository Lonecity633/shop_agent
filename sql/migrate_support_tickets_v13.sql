-- Migrate support_tickets from the initial human-handoff shape to the
-- buyer/seller/admin customer-service ticket shape.
-- Run this on databases that already have the older support_tickets table.

ALTER TABLE support_tickets RENAME COLUMN user_id TO buyer_id;
ALTER TABLE support_tickets RENAME COLUMN session_id TO source_session_id;
ALTER TABLE support_tickets RENAME COLUMN description TO content;
ALTER TABLE support_tickets RENAME COLUMN resolution TO reply_content;

ALTER TABLE support_tickets
    ADD COLUMN seller_id INT NULL AFTER buyer_id,
    ADD COLUMN admin_id INT NULL AFTER seller_id,
    ADD COLUMN ai_trace_id VARCHAR(120) NULL AFTER ai_summary;

UPDATE support_tickets
SET status = CASE status
    WHEN 'open' THEN 'pending'
    WHEN 'in_progress' THEN 'processing'
    WHEN 'resolved' THEN 'replied'
    WHEN 'rejected' THEN 'closed'
    ELSE status
END;

UPDATE support_tickets
SET category = CASE category
    WHEN 'product' THEN 'product_consultation'
    WHEN 'logistics' THEN 'logistics_issue'
    WHEN 'order' THEN 'logistics_issue'
    WHEN 'refund' THEN 'refund_issue'
    WHEN 'quality' THEN 'quality_issue'
    WHEN 'payment' THEN 'payment_issue'
    WHEN 'policy' THEN 'platform_rule'
    WHEN 'security' THEN 'platform_rule'
    ELSE category
END;

UPDATE support_tickets
SET seller_id = assigned_id
WHERE assigned_role = 'seller' AND assigned_id IS NOT NULL;

CREATE INDEX idx_support_tickets_buyer_id ON support_tickets (buyer_id);
CREATE INDEX idx_support_tickets_seller_id ON support_tickets (seller_id);
CREATE INDEX idx_support_tickets_admin_id ON support_tickets (admin_id);
CREATE INDEX idx_support_tickets_source_session_id ON support_tickets (source_session_id);
CREATE INDEX idx_support_tickets_ai_trace_id ON support_tickets (ai_trace_id);
