USE shop_db;

ALTER TABLE products
  ADD COLUMN image_urls TEXT NULL AFTER description;

UPDATE products
SET image_urls = '[]'
WHERE image_urls IS NULL;

ALTER TABLE products
  MODIFY COLUMN image_urls TEXT NOT NULL;
