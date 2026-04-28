USE shop_db;

CREATE TABLE IF NOT EXISTS seller_profiles (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL UNIQUE,
  shop_name VARCHAR(120) NOT NULL,
  shop_description TEXT NOT NULL,
  audit_status VARCHAR(20) NOT NULL DEFAULT 'pending',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_seller_profiles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT ck_seller_profiles_audit_status CHECK (audit_status IN ('pending', 'approved', 'rejected'))
);

CREATE INDEX idx_seller_profiles_audit_status ON seller_profiles(audit_status);
