-- 为 users 增加个人资料字段（头像/电话/昵称）
USE shop_db;

ALTER TABLE users
  ADD COLUMN display_name VARCHAR(60) NULL AFTER password_hash,
  ADD COLUMN phone VARCHAR(30) NULL AFTER display_name,
  ADD COLUMN avatar_url VARCHAR(512) NULL AFTER phone;

