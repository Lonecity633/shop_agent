-- 客服知识库多租户与角色分层（v10）
-- 1) 平台/商家知识库范围
-- 2) 适用角色分层
-- 3) 为商家知识库建立筛选索引

ALTER TABLE kb_documents
  ADD COLUMN scope VARCHAR(32) NOT NULL DEFAULT 'platform' AFTER source,
  ADD COLUMN seller_id INT NULL AFTER scope,
  ADD COLUMN audience VARCHAR(32) NOT NULL DEFAULT 'both' AFTER seller_id;

ALTER TABLE kb_documents
  ADD INDEX idx_kb_documents_scope (scope),
  ADD INDEX idx_kb_documents_seller_id (seller_id),
  ADD INDEX idx_kb_documents_audience (audience),
  ADD CONSTRAINT fk_kb_documents_seller_id
    FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE SET NULL;
