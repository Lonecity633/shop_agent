USE shop_db;

ALTER TABLE products
  ADD COLUMN seller_id BIGINT NULL AFTER id,
  ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'pending' AFTER price,
  ADD COLUMN review_note TEXT NOT NULL AFTER approval_status,
  ADD COLUMN reviewed_at DATETIME NULL AFTER review_note,
  ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER reviewed_at,
  ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

UPDATE products SET seller_id = 1 WHERE seller_id IS NULL;

ALTER TABLE products
  MODIFY seller_id BIGINT NOT NULL,
  ADD CONSTRAINT fk_products_seller FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE,
  ADD CONSTRAINT ck_products_approval_status CHECK (approval_status IN ('pending', 'approved', 'rejected'));

CREATE INDEX idx_products_seller_id ON products(seller_id);
CREATE INDEX idx_products_approval_status ON products(approval_status);
