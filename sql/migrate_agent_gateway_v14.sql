CREATE TABLE IF NOT EXISTS support_agent_memories (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  session_id VARCHAR(120) NOT NULL,
  summary TEXT NOT NULL,
  entities_json TEXT NOT NULL,
  recent_messages_json TEXT NOT NULL,
  last_route VARCHAR(64) NOT NULL DEFAULT '',
  last_tool_calls_json TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
  UNIQUE KEY uq_support_agent_memory_user_session (user_id, session_id),
  KEY idx_support_agent_memories_user (user_id),
  CONSTRAINT fk_support_agent_memories_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS support_followups (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  session_id VARCHAR(120) NOT NULL DEFAULT '',
  business_type VARCHAR(64) NOT NULL,
  business_id VARCHAR(120) NOT NULL DEFAULT '',
  idempotency_key VARCHAR(160) NOT NULL,
  due_at TIMESTAMP NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  payload_json TEXT NOT NULL,
  attempts INT NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
  UNIQUE KEY uq_support_followups_idempotency (idempotency_key),
  KEY idx_support_followups_due (status, due_at),
  KEY idx_support_followups_user_session (user_id, session_id),
  CONSTRAINT fk_support_followups_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS message_outbox (
  id INT AUTO_INCREMENT PRIMARY KEY,
  idempotency_key VARCHAR(160) NOT NULL,
  channel VARCHAR(64) NOT NULL DEFAULT 'in_app',
  recipient_user_id INT NULL,
  session_id VARCHAR(120) NOT NULL DEFAULT '',
  message_type VARCHAR(64) NOT NULL DEFAULT 'support_reply',
  payload_json TEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  attempts INT NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMP NULL,
  last_error TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
  UNIQUE KEY uq_message_outbox_idempotency (idempotency_key),
  KEY idx_message_outbox_delivery (status, next_attempt_at),
  KEY idx_message_outbox_recipient (recipient_user_id, session_id),
  CONSTRAINT fk_message_outbox_recipient FOREIGN KEY (recipient_user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
