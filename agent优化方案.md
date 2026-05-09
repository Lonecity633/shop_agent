# 京选商城 Agent 优化方案

## 项目技术栈总览

| 层级 | 技术 |
|------|------|
| **后端框架** | FastAPI + Uvicorn (async) |
| **ORM** | SQLAlchemy 2.0 (async, aiomysql) |
| **数据库** | MySQL 8.0 |
| **缓存** | Redis (async, Lua 脚本限流) |
| **认证** | JWT (python-jose) + pbkdf2_sha256 |
| **向量数据库** | ChromaDB (已引入，未实际使用) |
| **LLM 接入** | httpx 直连 OpenAI 兼容接口 (gpt-4o-mini) |
| **前端** | Vue 3 + Vite + Element Plus + Pinia |
| **部署** | Docker Compose (MySQL + Redis + Backend + Nginx) |

## Agent 现状分析

当前 agent 位于 `app/agent/`，是一个**手工编排的客服机器人**，核心问题：

1. **orchestrator.py 过于臃肿** (400 行) — 意图分类、路由、工具调用、prompt 管理全部耦合在一个类里
2. **LLM Client 无连接复用** — 每次请求 `async with httpx.AsyncClient()` 新建连接
3. **仅 1 个工具** (get_order_details) — product_inquiry 路径是手工注入上下文，未走 tool calling
4. **无 RAG 管线** — ChromaDB 和 LangChain 已装包但 `retrieval/` 是空目录
5. **无记忆/摘要机制** — history 只取最近 10 条 raw messages，长对话会丢失关键上下文
6. **无结构化日志/可观测性** — 没有 agent 调用链路的追踪

---

## 增量优化路线图（按优先级排序）

### Phase 1: 架构解耦（改动最小，收益最大）

#### 1.1 LLM Client 连接复用

```python
# llm_client.py — 改为类级别连接池
class LLMClient:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=...)  # 复用连接

    async def close(self):
        await self._client.aclose()
```

#### 1.2 Prompt 模板抽离

- 把散落在 orchestrator.py 里的 6 个 system prompt 字符串抽到 `app/agent/prompts/` 目录
- 每个意图一个文件 (order_query.md, policy.md, product.md, chitchat.md, classifier.md, guardrail.md)
- 方便后续版本管理和 A/B 测试

#### 1.3 Intent Router 抽象

```python
# app/agent/router.py
class IntentRouter:
    def __init__(self):
        self._handlers: dict[str, IntentHandler] = {}

    def register(self, intent: str, handler: IntentHandler): ...
    async def dispatch(self, intent: str, ctx: AgentContext) -> str: ...
```

把 4 个意图分支从 orchestrator 拆成独立 handler 类，orchestrator 只负责 guardrail -> classify -> route -> persist 的编排流程。

---

### Phase 2: 扩展 Tools（增加 Agent 自主能力）

#### 2.1 补齐商品工具定义

当前 product_inquiry 是手工拼 context，应改为标准 tool calling：

```python
SEARCH_PRODUCT_TOOL = {
    "type": "function",
    "function": {
        "name": "search_products",
        "description": "根据关键词搜索商品",
        "parameters": {
            "properties": {
                "keyword": {"type": "string"},
                "limit": {"type": "integer", "default": 5}
            }
        }
    }
}

GET_PRODUCT_DETAIL_TOOL = {
    "type": "function",
    "function": {
        "name": "get_product_detail",
        "description": "根据商品ID获取详情",
        "parameters": {
            "properties": {"product_id": {"type": "integer"}}
        }
    }
}
```

#### 2.2 新增退款查询工具

当前 refund 意图归入 order_query 但没有专门工具：

```python
GET_REFUND_STATUS_TOOL  # 查退款工单状态
```

#### 2.3 新增物流追踪工具

整合第三方物流 API 或从数据库查物流状态。

---

### Phase 3: RAG 知识库（政策问答准确率关键提升）

#### 3.1 实现 `app/agent/retrieval/`

数据库 schema 已有 `kb_documents`、`kb_chunks` 表：

```python
# retrieval/knowledge_base.py
class KnowledgeBase:
    async def ingest(self, docs: list[Document]): ...      # 切分 + 写入 ChromaDB
    async def retrieve(self, query: str, top_k: int = 3): ... # 向量检索
```

#### 3.2 政策文档灌入

把平台规则、退换货政策、运费规则等文档 chunk 后写入 ChromaDB。

#### 3.3 policy_query 路径改造

先 RAG retrieve，把 top-k chunks 注入 prompt，而非让 LLM 凭空回答。

---

### Phase 4: 对话记忆增强

#### 4.1 滑动窗口 + 摘要

当前取最近 10 条 raw messages，长对话丢失上下文：

```python
# agent/memory.py
class ConversationMemory:
    async def get_context(self, db, session_id, max_tokens=2000):
        # 1. 取最近 N 条
        # 2. 如果超 token 限制，对早期消息做摘要
        # 3. 返回 [summary] + [recent messages]
```

#### 4.2 关键信息槽位提取

从对话中提取并缓存：订单号、商品ID、用户诉求，避免反复追问。

---

### Phase 5: 可观测性 & 质量

#### 5.1 结构化日志

记录每次 agent 调用链路：

```json
{
    "session_id": 123,
    "intent": "order_query",
    "tools_called": ["get_order_details"],
    "llm_latency_ms": [800, 600],
    "total_latency_ms": 1500,
    "tokens_used": {}
}
```

#### 5.2 意图分类准确率追踪

存入 DB，定期 review 误分类 case，迭代 prompt。

---

### Phase 6: 前端体验升级

#### 6.1 打字机效果 (SSE)

当前前端等 LLM 全量返回后才显示，改为 Server-Sent Events 流式输出。

#### 6.2 卖家端客服入口

当前只有买家端 `SupportChatView.vue`，卖家侧缺失。

#### 6.3 快捷问题卡片

在聊天界面底部加预设按钮："查订单"、"退换货政策"、"商品推荐"。

---

## 推荐实施顺序

| 优先级 | 阶段 | 工作量 | 收益 |
|--------|------|--------|------|
| P0 | 1.1 LLM 连接复用 | 0.5 天 | 性能 + 稳定性 |
| P0 | 1.2 Prompt 抽离 | 0.5 天 | 可维护性 |
| P1 | 1.3 Intent Router 重构 | 1 天 | 可扩展性 |
| P1 | 2.1-2.2 补齐 Tools | 1 天 | Agent 自主能力 |
| P2 | 3.1-3.3 RAG 知识库 | 2-3 天 | 政策问答质量飞跃 |
| P2 | 4.1 对话记忆 | 1 天 | 长对话体验 |
| P3 | 5.1 结构化日志 | 1 天 | 运维可观测 |
| P3 | 6.1 SSE 流式输出 | 1-2 天 | 用户体验 |

**Phase 1+2 大约 3-4 天可以完成，是投入产出比最高的起点。**
