-- 将旧 users(id, username, email) 升级为认证所需结构
USE shop_db;

-- 1) 删除旧 username 列（如果不存在请忽略此行报错）
ALTER TABLE users DROP COLUMN username;

-- 2) 新增密码哈希列
ALTER TABLE users
  ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT '' AFTER email;

-- 3) 新增角色列（buyer/seller/admin）
ALTER TABLE users
  ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'buyer' AFTER password_hash;

-- 4) 新增时间戳
ALTER TABLE users
  ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER role,
  ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

-- 5) 角色约束（MySQL 8.0.16+ 生效）
ALTER TABLE users
  ADD CONSTRAINT ck_users_role_valid CHECK (role IN ('buyer', 'seller', 'admin'));

-- 6) 建议索引
CREATE INDEX idx_users_role ON users(role);

-- 注意：旧用户 password_hash 为空字符串，无法登录。
-- 你可以执行重置密码逻辑，或只保留新注册用户用于联调。
