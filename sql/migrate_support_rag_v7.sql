-- 智能客服 RAG 最小底座（v7）
-- 目标：
-- 1) 新增知识库文档与切片表
-- 2) 新增客服多轮消息表
-- 3) 新增检索证据追踪表

CREATE TABLE IF NOT EXISTS kb_documents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  source VARCHAR(512) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  INDEX idx_kb_documents_title (title),
  INDEX idx_kb_documents_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS kb_chunks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  document_id INT NOT NULL,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  vector_id VARCHAR(255) NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  INDEX idx_kb_chunks_document_id (document_id),
  CONSTRAINT fk_kb_chunks_document_id
    FOREIGN KEY (document_id) REFERENCES kb_documents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS support_messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  session_id INT NOT NULL,
  role VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  retrieval_query TEXT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  INDEX idx_support_messages_session_id (session_id),
  INDEX idx_support_messages_role (role),
  CONSTRAINT fk_support_messages_session_id
    FOREIGN KEY (session_id) REFERENCES support_sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS support_retrieval_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  session_id INT NOT NULL,
  message_id INT NULL,
  document_id INT NULL,
  chunk_id INT NULL,
  score DECIMAL(8,4) NULL,
  is_cited TINYINT(1) NOT NULL DEFAULT 0,
  payload_json TEXT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  INDEX idx_support_retrieval_logs_session_id (session_id),
  INDEX idx_support_retrieval_logs_message_id (message_id),
  INDEX idx_support_retrieval_logs_document_id (document_id),
  INDEX idx_support_retrieval_logs_chunk_id (chunk_id),
  INDEX idx_support_retrieval_logs_is_cited (is_cited),
  CONSTRAINT fk_support_retrieval_logs_session_id
    FOREIGN KEY (session_id) REFERENCES support_sessions(id) ON DELETE CASCADE,
  CONSTRAINT fk_support_retrieval_logs_message_id
    FOREIGN KEY (message_id) REFERENCES support_messages(id) ON DELETE SET NULL,
  CONSTRAINT fk_support_retrieval_logs_document_id
    FOREIGN KEY (document_id) REFERENCES kb_documents(id) ON DELETE SET NULL,
  CONSTRAINT fk_support_retrieval_logs_chunk_id
    FOREIGN KEY (chunk_id) REFERENCES kb_chunks(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
