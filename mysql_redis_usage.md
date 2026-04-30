# MySQL 与 Redis 在当前项目中的使用说明

## 1. MySQL 用在了哪里

### 1.1 配置与连接层
- 配置项定义：`app/core/config.py`
  - `mysql_host` / `mysql_port` / `mysql_user` / `mysql_password` / `mysql_db`
  - `sqlalchemy_database_uri` 组装出 `mysql+aiomysql://...`
- 数据库会话与引擎：`app/db/session.py`
  - `create_async_engine(settings.sqlalchemy_database_uri, ...)`
  - `AsyncSessionLocal` 与 `get_db()` 作为全局数据库会话依赖
- 启动初始化：`app/db/init_db.py`
  - `Base.metadata.create_all` 在启动时创建模型对应表
- 本地依赖容器：`docker-compose.yml`
  - `mysql:8.4` 服务，端口 `3306`，数据卷 `mysql_data`

### 1.2 业务数据存储层
MySQL 是项目的主存储，承载全部核心业务实体（位于 `app/models/`）及其 CRUD 读写（位于 `app/crud/`），包括但不限于：
- 用户与权限：`user.py`
- 商品与分类：`product.py`、`category.py`
- 订单与状态流转：`order.py`
- 退款：`refund.py`
- 地址、购物车、收藏、评论：`address.py`、`cart.py`、`favorite.py`、`comment.py`
- 卖家资料审核：`seller_profile.py`
- 客服与知识库：`support.py`、`kb.py`
- 审计日志：`operation_audit.py`

后端路由层通过依赖注入 `get_db()` 获取 `AsyncSession`，在 `app/api/routers/*.py -> app/services/*.py -> app/crud/*.py` 链路中完成所有业务读写。

### 1.3 MySQL 解决了什么问题
- 解决“核心交易数据持久化”问题：订单、商品、用户等需要可靠落库与长期保存。
- 解决“复杂关系建模”问题：用户-订单-商品-卖家等关系由关系型模型与外键约束管理。
- 解决“一致性与可审计”问题：订单状态、退款流程、操作日志可在统一事务与模型体系中追踪。
- 解决“统一数据访问”问题：通过 SQLAlchemy AsyncSession 统一 CRUD 范式，降低各模块数据访问分散度。

---

## 2. Redis 用在了哪里

### 2.1 配置与客户端生命周期
- 配置项定义：`app/core/config.py`
  - `redis_host` / `redis_port` / `redis_db` / `redis_key_prefix`
  - 限流与降级开关：`login_rate_limit_*`、`order_rate_limit_*`、`auth_fail_closed`
- 客户端封装：`app/core/redis_client.py`
  - `init_redis()`、`get_redis()`、`close_redis()`
- 应用启动生命周期：`app/main.py`
  - 启动时初始化 Redis，失败时根据 `auth_fail_closed` 决定是否拒绝服务启动
- 本地依赖容器：`docker-compose.yml`
  - `redis:7-alpine` 服务，端口 `6379`，AOF 持久化 `--appendonly yes`

### 2.2 具体业务使用点
1. 登录/下单限流（防刷）
- 通用限流实现：`app/core/rate_limit.py`
  - 基于 `INCR + EXPIRE` 固定窗口计数
  - Key 形如：`{prefix}:ratelimit:{业务键}`
- 登录限流：`app/services/auth.py` 的 `login_user()`
  - 维度：`login:{client_ip}:{email}`
- 下单限流：`app/services/order.py` 的 `create_order()`
  - 维度：`order:{user_id}`

2. JWT 登出黑名单（令牌失效）
- 鉴权校验黑名单：`app/services/auth.py` 的 `resolve_current_user()`
  - 读取 `shop:blacklist:{jti}`，若存在则拒绝访问
- 登出写入黑名单：`app/services/auth.py` 的 `logout_token()`
  - `setex(blacklist_key, ttl, "1")`，TTL 与 token 剩余有效期一致

### 2.3 Redis 解决了什么问题
- 解决“无状态 JWT 难以主动失效”问题：通过黑名单让登出后的 token 立即失效。
- 解决“高频请求防刷”问题：登录和下单频控降低撞库、暴力尝试和恶意下单风险。
- 解决“高并发计数性能”问题：Redis 原子自增适合短窗口限流，避免把高频计数压力打到 MySQL。
- 解决“鉴权依赖可控降级”问题：`auth_fail_closed` 支持故障时 fail-close/fail-open 策略切换。

---

## 3. 总结（按职责划分）
- MySQL：负责“业务真相数据”（交易、用户、商品、流程、审计）的持久化与关系一致性。
- Redis：负责“鉴权与风控辅助能力”（黑名单、限流）的实时判定与高性能计数。

两者组合形成：MySQL 保证核心数据可靠，Redis 保证认证风控实时与抗压。
