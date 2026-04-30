-- 基础测试数据（可重复导入）
-- 账号密码统一为: 123456

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 1;

START TRANSACTION;

-- categories
INSERT INTO categories (id, name, sort_order, is_active)
VALUES
  (2001, 'Seed-数码', 10, 1),
  (2002, 'Seed-家居', 20, 1),
  (2003, 'Seed-食品', 30, 1)
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  sort_order = VALUES(sort_order),
  is_active = VALUES(is_active);

-- users (password: 123456)
INSERT INTO users (id, email, password_hash, display_name, phone, avatar_url, role)
VALUES
  (1001, 'seed_admin@example.com', '$pbkdf2-sha256$29000$8n6Pce5dy/m/l3KuFYIwxg$MEJ3i/4dNPlDhjn1SNRtbB5LYEPKl1nYoJIZ7kD/cXA', 'Seed Admin', '13800000001', 'https://example.com/avatar/admin.png', 'admin'),
  (1002, 'seed_seller_a@example.com', '$pbkdf2-sha256$29000$8n6Pce5dy/m/l3KuFYIwxg$MEJ3i/4dNPlDhjn1SNRtbB5LYEPKl1nYoJIZ7kD/cXA', 'Seed Seller A', '13800000002', 'https://example.com/avatar/seller_a.png', 'seller'),
  (1003, 'seed_seller_b@example.com', '$pbkdf2-sha256$29000$8n6Pce5dy/m/l3KuFYIwxg$MEJ3i/4dNPlDhjn1SNRtbB5LYEPKl1nYoJIZ7kD/cXA', 'Seed Seller B', '13800000003', 'https://example.com/avatar/seller_b.png', 'seller'),
  (1004, 'seed_buyer_a@example.com', '$pbkdf2-sha256$29000$8n6Pce5dy/m/l3KuFYIwxg$MEJ3i/4dNPlDhjn1SNRtbB5LYEPKl1nYoJIZ7kD/cXA', 'Seed Buyer A', '13800000004', 'https://example.com/avatar/buyer_a.png', 'buyer'),
  (1005, 'seed_buyer_b@example.com', '$pbkdf2-sha256$29000$8n6Pce5dy/m/l3KuFYIwxg$MEJ3i/4dNPlDhjn1SNRtbB5LYEPKl1nYoJIZ7kD/cXA', 'Seed Buyer B', '13800000005', 'https://example.com/avatar/buyer_b.png', 'buyer')
ON DUPLICATE KEY UPDATE
  email = VALUES(email),
  password_hash = VALUES(password_hash),
  display_name = VALUES(display_name),
  phone = VALUES(phone),
  avatar_url = VALUES(avatar_url),
  role = VALUES(role);

-- seller profiles
INSERT INTO seller_profiles (id, user_id, shop_name, shop_description, audit_status, is_active)
VALUES
  (1101, 1002, 'Seed 3C 官方店', '提供测试用数码商品', 'approved', 1),
  (1102, 1003, 'Seed 家居旗舰店', '提供测试用家居商品', 'approved', 1)
ON DUPLICATE KEY UPDATE
  user_id = VALUES(user_id),
  shop_name = VALUES(shop_name),
  shop_description = VALUES(shop_description),
  audit_status = VALUES(audit_status),
  is_active = VALUES(is_active);

-- products
INSERT INTO products (
  id, seller_id, category_id, name, description, image_urls, stock, price,
  approval_status, review_note, reviewed_at
)
VALUES
  (3001, 1002, 2001, 'Seed 蓝牙耳机', '降噪蓝牙耳机，测试数据', '["https://picsum.photos/seed/p3001/800/600"]', 120, 199.00, 'approved', '审核通过', NOW()),
  (3002, 1003, 2002, 'Seed 人体工学椅', '可调节靠背，测试数据', '["https://picsum.photos/seed/p3002/800/600"]', 60, 599.00, 'approved', '审核通过', NOW()),
  (3003, 1002, 2001, 'Seed 智能手表', '待审核商品示例', '["https://picsum.photos/seed/p3003/800/600"]', 45, 399.00, 'pending', '', NULL),
  (3004, 1003, 2003, 'Seed 组合零食包', '已驳回商品示例', '["https://picsum.photos/seed/p3004/800/600"]', 80, 69.00, 'rejected', '包装信息不完整', NOW())
ON DUPLICATE KEY UPDATE
  seller_id = VALUES(seller_id),
  category_id = VALUES(category_id),
  name = VALUES(name),
  description = VALUES(description),
  image_urls = VALUES(image_urls),
  stock = VALUES(stock),
  price = VALUES(price),
  approval_status = VALUES(approval_status),
  review_note = VALUES(review_note),
  reviewed_at = VALUES(reviewed_at);

-- addresses
INSERT INTO user_addresses (
  id, user_id, receiver_name, receiver_phone, province, city, district, detail_address, is_default
)
VALUES
  (4001, 1004, '张三', '13900000001', '上海市', '上海市', '浦东新区', '世纪大道 100 号', 1),
  (4002, 1004, '张三(公司)', '13900000002', '上海市', '上海市', '徐汇区', '漕溪北路 200 号', 0),
  (4003, 1005, '李四', '13900000003', '北京市', '北京市', '海淀区', '中关村大街 1 号', 1)
ON DUPLICATE KEY UPDATE
  user_id = VALUES(user_id),
  receiver_name = VALUES(receiver_name),
  receiver_phone = VALUES(receiver_phone),
  province = VALUES(province),
  city = VALUES(city),
  district = VALUES(district),
  detail_address = VALUES(detail_address),
  is_default = VALUES(is_default);

-- cart items
INSERT INTO cart_items (id, user_id, product_id, quantity, selected)
VALUES
  (4101, 1004, 3002, 1, 1),
  (4102, 1005, 3001, 2, 1)
ON DUPLICATE KEY UPDATE
  user_id = VALUES(user_id),
  product_id = VALUES(product_id),
  quantity = VALUES(quantity),
  selected = VALUES(selected);

-- favorites
INSERT INTO favorites (id, user_id, product_id)
VALUES
  (4201, 1004, 3001),
  (4202, 1004, 3002),
  (4203, 1005, 3002)
ON DUPLICATE KEY UPDATE
  user_id = VALUES(user_id),
  product_id = VALUES(product_id);

-- orders
INSERT INTO orders (
  id, order_no, user_id, product_id, status, pay_status, total_price, pay_amount, pay_channel,
  paid_at, close_reason, inventory_reverted, address_snapshot,
  tracking_no, logistics_company, shipped_at, received_at
)
VALUES
  (5001, 'SO20260430000000005001', 1004, 3001, 'pending_paid', 'pending', 199.00, 199.00, 'simulated', NULL, '', 0,
   '{"address_id":4001,"receiver_name":"张三","receiver_phone":"13900000001","province":"上海市","city":"上海市","district":"浦东新区","detail_address":"世纪大道 100 号"}',
   '', '', NULL, NULL),
  (5002, 'SO20260430000000005002', 1004, 3002, 'completed', 'paid', 1198.00, 1198.00, 'simulated', DATE_SUB(NOW(), INTERVAL 3 DAY), '', 0,
   '{"address_id":4001,"receiver_name":"张三","receiver_phone":"13900000001","province":"上海市","city":"上海市","district":"浦东新区","detail_address":"世纪大道 100 号"}',
   'SF123456789CN', '顺丰速运', DATE_SUB(NOW(), INTERVAL 2 DAY), DATE_SUB(NOW(), INTERVAL 1 DAY)),
  (5003, 'SO20260430000000005003', 1005, 3001, 'cancelled', 'refunded', 199.00, 199.00, 'simulated', DATE_SUB(NOW(), INTERVAL 4 DAY), '退款完成', 1,
   '{"address_id":4003,"receiver_name":"李四","receiver_phone":"13900000003","province":"北京市","city":"北京市","district":"海淀区","detail_address":"中关村大街 1 号"}',
   '', '', NULL, NULL)
ON DUPLICATE KEY UPDATE
  order_no = VALUES(order_no),
  user_id = VALUES(user_id),
  product_id = VALUES(product_id),
  status = VALUES(status),
  pay_status = VALUES(pay_status),
  total_price = VALUES(total_price),
  pay_amount = VALUES(pay_amount),
  pay_channel = VALUES(pay_channel),
  paid_at = VALUES(paid_at),
  close_reason = VALUES(close_reason),
  inventory_reverted = VALUES(inventory_reverted),
  address_snapshot = VALUES(address_snapshot),
  tracking_no = VALUES(tracking_no),
  logistics_company = VALUES(logistics_company),
  shipped_at = VALUES(shipped_at),
  received_at = VALUES(received_at);

-- order items
INSERT INTO order_items (
  id, order_id, product_id, product_name_snapshot, unit_price_snapshot, quantity, subtotal
)
VALUES
  (6001, 5001, 3001, 'Seed 蓝牙耳机', 199.00, 1, 199.00),
  (6002, 5002, 3002, 'Seed 人体工学椅', 599.00, 2, 1198.00),
  (6003, 5003, 3001, 'Seed 蓝牙耳机', 199.00, 1, 199.00)
ON DUPLICATE KEY UPDATE
  order_id = VALUES(order_id),
  product_id = VALUES(product_id),
  product_name_snapshot = VALUES(product_name_snapshot),
  unit_price_snapshot = VALUES(unit_price_snapshot),
  quantity = VALUES(quantity),
  subtotal = VALUES(subtotal);

-- order status logs
INSERT INTO order_status_logs (
  id, order_id, from_status, to_status, actor_id, actor_role, reason, created_at
)
VALUES
  (6101, 5002, 'pending_paid', 'paid', 1004, 'buyer', '买家完成支付', DATE_SUB(NOW(), INTERVAL 3 DAY)),
  (6102, 5002, 'paid', 'shipped', 1003, 'seller', '卖家发货', DATE_SUB(NOW(), INTERVAL 2 DAY)),
  (6103, 5002, 'shipped', 'completed', 1004, 'buyer', '买家确认收货', DATE_SUB(NOW(), INTERVAL 1 DAY)),
  (6104, 5003, 'pending_paid', 'paid', 1005, 'buyer', '买家完成支付', DATE_SUB(NOW(), INTERVAL 4 DAY)),
  (6105, 5003, 'paid', 'cancelled', 1001, 'admin', '退款完成后关闭订单', DATE_SUB(NOW(), INTERVAL 1 DAY))
ON DUPLICATE KEY UPDATE
  order_id = VALUES(order_id),
  from_status = VALUES(from_status),
  to_status = VALUES(to_status),
  actor_id = VALUES(actor_id),
  actor_role = VALUES(actor_role),
  reason = VALUES(reason),
  created_at = VALUES(created_at);

-- comments
INSERT INTO comments (id, order_id, product_id, user_id, rating, content)
VALUES
  (6201, 5002, 3002, 1004, 5, '椅子很舒服，物流很快，测试评论。')
ON DUPLICATE KEY UPDATE
  order_id = VALUES(order_id),
  product_id = VALUES(product_id),
  user_id = VALUES(user_id),
  rating = VALUES(rating),
  content = VALUES(content);

-- refund tickets
INSERT INTO refund_tickets (
  id, order_id, buyer_id, seller_id, status, amount, reason, buyer_note,
  seller_note, admin_note, fail_reason, processed_at
)
VALUES
  (7001, 5003, 1005, 1002, 'refunded', 199.00, '商品与描述不符', '申请全额退款',
   '同意退款', '管理员审核通过并执行', '', DATE_SUB(NOW(), INTERVAL 1 DAY))
ON DUPLICATE KEY UPDATE
  order_id = VALUES(order_id),
  buyer_id = VALUES(buyer_id),
  seller_id = VALUES(seller_id),
  status = VALUES(status),
  amount = VALUES(amount),
  reason = VALUES(reason),
  buyer_note = VALUES(buyer_note),
  seller_note = VALUES(seller_note),
  admin_note = VALUES(admin_note),
  fail_reason = VALUES(fail_reason),
  processed_at = VALUES(processed_at);

-- operation audits
INSERT INTO operation_audits (
  id, entity_type, entity_id, action, actor_id, actor_role, before_state, after_state, reason
)
VALUES
  (7301, 'order', 5002, 'order_completed', 1004, 'buyer',
   '{"status":"shipped"}', '{"status":"completed"}', '买家确认收货'),
  (7302, 'refund', 7001, 'refund_executed_success', 1001, 'admin',
   '{"status":"approved_pending_refund"}', '{"status":"refunded"}', '管理员执行退款成功')
ON DUPLICATE KEY UPDATE
  entity_type = VALUES(entity_type),
  entity_id = VALUES(entity_id),
  action = VALUES(action),
  actor_id = VALUES(actor_id),
  actor_role = VALUES(actor_role),
  before_state = VALUES(before_state),
  after_state = VALUES(after_state),
  reason = VALUES(reason);

-- kb documents
INSERT INTO kb_documents (id, title, source, status)
VALUES
  (8001, '售后退款规则（Seed）', 'internal://seed/refund-policy', 'active'),
  (8002, '物流时效说明（Seed）', 'internal://seed/logistics-policy', 'active')
ON DUPLICATE KEY UPDATE
  title = VALUES(title),
  source = VALUES(source),
  status = VALUES(status);

-- kb chunks
INSERT INTO kb_chunks (id, document_id, chunk_index, content, vector_id, metadata_json)
VALUES
  (8101, 8001, 1, '已支付未发货订单支持退款申请；发货后需走售后仲裁流程。', 'vec-seed-8101', '{"topic":"refund"}'),
  (8102, 8001, 2, '退款执行成功后，订单状态会更新为 cancelled，支付状态更新为 refunded。', 'vec-seed-8102', '{"topic":"refund"}'),
  (8103, 8002, 1, '默认物流时效 24-72 小时，节假日可能顺延。', 'vec-seed-8103', '{"topic":"logistics"}')
ON DUPLICATE KEY UPDATE
  document_id = VALUES(document_id),
  chunk_index = VALUES(chunk_index),
  content = VALUES(content),
  vector_id = VALUES(vector_id),
  metadata_json = VALUES(metadata_json);

-- support sessions
INSERT INTO support_sessions (id, operator_id, user_id, question, answer, queried_entities, created_at)
VALUES
  (9001, 1001, 1004, '订单5002什么时候到？', '订单已签收。',
   '[{"type":"order","id":5002},{"type":"kb_chunk","id":8103}]', DATE_SUB(NOW(), INTERVAL 12 HOUR))
ON DUPLICATE KEY UPDATE
  operator_id = VALUES(operator_id),
  user_id = VALUES(user_id),
  question = VALUES(question),
  answer = VALUES(answer),
  queried_entities = VALUES(queried_entities),
  created_at = VALUES(created_at);

-- support messages
INSERT INTO support_messages (id, session_id, role, content, retrieval_query, created_at)
VALUES
  (9101, 9001, 'user', '订单5002物流到哪了？', '订单5002 物流状态', DATE_SUB(NOW(), INTERVAL 12 HOUR)),
  (9102, 9001, 'assistant', '系统显示订单5002已完成签收。', '订单5002 状态 + 物流时效', DATE_SUB(NOW(), INTERVAL 11 HOUR))
ON DUPLICATE KEY UPDATE
  session_id = VALUES(session_id),
  role = VALUES(role),
  content = VALUES(content),
  retrieval_query = VALUES(retrieval_query),
  created_at = VALUES(created_at);

-- support retrieval logs
INSERT INTO support_retrieval_logs (
  id, session_id, message_id, document_id, chunk_id, score, is_cited, payload_json, created_at
)
VALUES
  (9201, 9001, 9102, 8002, 8103, 0.9234, 1, '{"source":"kb","reason":"logistics policy"}', DATE_SUB(NOW(), INTERVAL 11 HOUR)),
  (9202, 9001, 9102, 8001, 8102, 0.8120, 0, '{"source":"kb","reason":"refund state sync"}', DATE_SUB(NOW(), INTERVAL 11 HOUR))
ON DUPLICATE KEY UPDATE
  session_id = VALUES(session_id),
  message_id = VALUES(message_id),
  document_id = VALUES(document_id),
  chunk_id = VALUES(chunk_id),
  score = VALUES(score),
  is_cited = VALUES(is_cited),
  payload_json = VALUES(payload_json),
  created_at = VALUES(created_at);

COMMIT;
