# FastAPI Shop Agent Backend

## 1. 项目结构

```text
.
├── app
│   ├── api
│   │   ├── router.py
│   │   └── routers
│   │       ├── order.py
│   │       └── product.py
│   ├── core
│   │   └── config.py
│   ├── crud
│   │   ├── order.py
│   │   └── product.py
│   ├── db
│   │   ├── base.py
│   │   ├── init_db.py
│   │   └── session.py
│   ├── models
│   │   ├── order.py
│   │   ├── product.py
│   │   └── user.py
│   ├── schemas
│   │   ├── common.py
│   │   ├── order.py
│   │   └── product.py
│   └── main.py
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## 2. 启动本地依赖

```bash
docker compose up -d
```

## 3. 安装依赖并启动 API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## 4. 接口文档

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## 5. 关键接口（v2）

- `POST /api/auth/register`、`POST /api/auth/login`、`POST /api/auth/logout` 认证流程
- `POST /api/v1/seller/products` 卖家上架商品（需店铺资料审核通过）
- `PATCH /api/v1/products/{product_id}/audit` 管理员审核商品
- `POST /api/v1/orders` 买家下单
- `POST /api/v1/orders/{order_id}/ship` 卖家发货
- `POST /api/v1/orders/{order_id}/receive` 买家确认收货（自动完成订单）
- `POST /api/v1/orders/{order_id}/comments` 买家评论
- `GET /api/v1/orders/{order_id}/logs` 订单状态变更审计日志
- `GET /api/v1/admin/seller-profiles/pending`、`PATCH /api/v1/admin/seller-profiles/{id}/audit` 卖家资料审核
- `POST /api/v1/support/kb/documents`、`GET /api/v1/support/kb/documents` 客服知识库文档管理
- `POST /api/v1/support/sessions/{session_id}/messages`、`GET /api/v1/support/sessions/{session_id}/messages` 客服会话消息
- `GET /api/v1/support/sessions/{session_id}/evidence` 客服检索证据链

统一返回结构：

```json
{
  "message": "描述信息",
  "data": {}
}
```
