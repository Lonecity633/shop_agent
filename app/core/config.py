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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def sqlalchemy_database_uri(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )


settings = Settings()
