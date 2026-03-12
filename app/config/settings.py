"""Pydantic BaseSettings — all config loaded from environment."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "TraderFlow"
    environment: str = Field("development", pattern="^(development|staging|production)$")
    debug: bool = False

    database_url: str = ""
    database_replica_url: str = ""
    database_pool_size: int = 20
    database_max_overflow: int = 10

    redis_url: str = "redis://localhost:6379"
    redis_db_cache: int = 0
    redis_db_celery: int = 1
    redis_db_idempotency: int = 2
    redis_db_rate_limit: int = 3
    redis_db_sessions: int = 4

    momo_base_url: str = "https://sandbox.momodeveloper.mtn.com"
    momo_subscription_key: str = ""
    momo_webhook_secret: str = ""
    momo_environment: str = "sandbox"
    momo_poll_interval_seconds: int = 300

    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "reports@traderflow.com"

    hubtel_client_id: str = ""
    hubtel_client_secret: str = ""
    hubtel_sender_id: str = "TraderFlow"

    aws_region: str = "eu-west-1"
    s3_bucket_reports: str = ""
    s3_bucket_kyc_docs: str = ""

    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-5"

    aml_large_tx_threshold_ghs: str = "5000.00"
    aml_velocity_max_per_hour: int = 10
    aml_zscore_threshold: float = 3.0

    firebase_credentials_json: str = "{}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
