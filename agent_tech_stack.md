# Agent 技术栈总结

这是一个电商客服 AI Agent 系统，以下是用到的核心技术：

## 1. Agent 架构模式

- **意图分类 + 多处理器分发**：用户消息先通过 LLM 做意图分类（4类：订单查询、政策咨询、商品咨询、闲聊），再路由到对应 Handler 处理
- **编排器模式**：`SupportAgentOrchestrator` 作为统一入口，串联 guardrail → 意图分类 → 路由 → 响应生成的完整流程

## 2. LLM 集成

- 直接用 `httpx` 调用 OpenAI 兼容的 `/chat/completions` 接口，**没有用 LangChain 的链式调用**（虽然依赖里有 langchain，实际未使用）
- 默认模型 `gpt-4o-mini`，temperature 0.2
- 支持 OpenAI 的 **Function Calling**（tool_choice="auto"），用于订单查询时让 LLM 自主决定是否调用工具

## 3. MCP（Model Context Protocol）

- 服务端用 `FastMCP` 起独立进程，暴露 4 个工具（订单查询、商品快照、商品搜索、政策知识库查询）
- 客户端用 `mcp.client.streamable_http` 调用，transport 是 streamable-http
- **MCP 优先，本地 DB 直查作为降级方案**

## 4. RAG（检索增强生成）

- **向量数据库**：ChromaDB，cosine 相似度
- **Embedding**：`text-embedding-3-small`（OpenAI 兼容接口）
- **文本切分**：段落感知分块，500 字符/块，50 字符重叠
- **检索流程**：query embedding → ChromaDB 向量搜索 → 回查 MySQL 拿完整内容 → 注入 prompt 生成回答
- 用于政策类问题的回答，prompt 里强调"只用检索到的文档回答，不编造"

## 5. 会话记忆

- 维护最近 10 条消息的窗口
- 超过 15 条时触发 LLM 自动摘要（200 字第三人称摘要），压缩历史

## 6. 安全防护

- **Guardrail**：正则匹配敏感词（密码、银行卡、CVV、身份证），命中直接拦截
- **限流**：Redis + Lua 脚本实现双窗口限流（10 秒/5 次 + 60 秒/20 次）
- **MCP 认证**：每次工具调用需要 user_id + user_role + internal_secret
- **RBAC**：订单查询按角色隔离（买家看自己的、卖家看自己商品的、管理员看所有）

## 7. 数据持久化

- MySQL 8.0 + SQLAlchemy 2.0（async，aiomysql 驱动）
- 对话记录、工具调用记录、检索日志、审计日志全部入库

## 面试亮点建议

| 可以展开讲的点 | 关键词 |
|---|---|
| 为什么用 MCP 而不是直接查 DB | 解耦、可独立部署、标准化工具协议、便于多 agent 共享 |
| RAG 的分块策略 | 段落感知、overlap 防断句、向量+元数据双存储 |
| 两轮 LLM 调用（订单查询） | 第一轮 tool calling 决策，第二轮整合工具结果生成回答 |
| 降级策略 | MCP 失败 → 本地 DB 直查；LLM 超时 → 预设 fallback 回复 |
| 会话摘要压缩 | 防止上下文窗口溢出，平衡信息保留与 token 成本 |
