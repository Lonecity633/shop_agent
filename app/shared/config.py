from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "shop-agent-backend"
    app_env: str = "dev"
    api_v1_str: str = "/api/v1"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "shop_user"
    mysql_password: str = "shop_pass"
    mysql_db: str = "shop_db"

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_issuer: str = "shop-agent"

    redis_key_prefix: str = "shop"
    login_rate_limit_count: int = 10
    login_rate_limit_window_seconds: int = 60
    order_rate_limit_count: int = 20
    order_rate_limit_window_seconds: int = 60
    support_reply_short_rate_limit_count: int = 5
    support_reply_short_rate_limit_window_seconds: int = 10
    support_reply_long_rate_limit_count: int = 20
    support_reply_long_rate_limit_window_seconds: int = 60
    support_reply_rate_limit_fail_closed: bool = False
    auth_fail_closed: bool = True
    jwt_require_strong_secret: bool = True
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 30
    llm_temperature: float = 0.2
    llm_trust_env: bool = False

    mcp_server_url: str = "http://localhost:8002/mcp"
    mcp_internal_secret: str = "change-this-in-production"
    mcp_tool_timeout_seconds: int = 5
    mcp_fallback_enabled: bool = True
    mcp_server_host: str = "0.0.0.0"
    mcp_server_port: int = 8002

    backend_base_url: str = "http://localhost:8000"
    agent_base_url: str = "http://localhost:8001"
    agent_service_port: int = 8001
    backend_service_port: int = 8000

    support_agent_loop_enabled: bool | None = None
    support_agent_loop_max_steps: int | None = None
    support_agent_loop_tool_cache_seconds: int | None = None
    support_memory_recent_messages: int = 12
    support_memory_summary_trigger_messages: int = 16
    support_memory_summary_max_chars: int = 800
    support_memory_persist_path: str = ""
    support_mcp_retry_attempts: int = 2
    support_mcp_retry_backoff_seconds: float = 0.2

    # Legacy names kept for existing .env/deployments; prefer support_agent_loop_*.
    support_react_enabled: bool = True
    support_llm_routing_enabled: bool = True
    support_react_max_steps: int = 4
    support_react_tool_cache_seconds: int = 60
    # Legacy unused ReAct-era fields kept only to avoid breaking old config.
    support_react_trigger_confidence: float = 0.65
    support_react_allowed_tools: str = (
        "get_order_details,get_product_snapshot,search_products,query_policy_kb,"
        "create_support_ticket,escalate_ticket_to_admin"
    )

    support_chroma_persist_dir: str = "./data/chroma"
    support_chroma_collection: str = "support_kb_chunks"
    support_retrieval_top_k: int = 5
    embedding_model: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def sqlalchemy_database_uri(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @property
    def agent_loop_enabled(self) -> bool:
        if self.support_agent_loop_enabled is not None:
            return self.support_agent_loop_enabled
        return self.support_react_enabled

    @property
    def agent_loop_max_steps(self) -> int:
        if self.support_agent_loop_max_steps is not None:
            return self.support_agent_loop_max_steps
        return self.support_react_max_steps

    @property
    def agent_loop_tool_cache_seconds(self) -> int:
        if self.support_agent_loop_tool_cache_seconds is not None:
            return self.support_agent_loop_tool_cache_seconds
        return self.support_react_tool_cache_seconds


settings = Settings()
