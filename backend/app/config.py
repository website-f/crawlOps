from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://crawlops:crawlops_dev@postgres:5432/crawlops"
    redis_url: str = "redis://redis:6379/0"
    meili_url: str = "http://meilisearch:7700"
    meili_master_key: str = "crawlops_meili_dev_key"
    minio_url: str = "http://minio:9000"
    minio_root_user: str = "crawlops"
    minio_root_password: str = "crawlops_dev_secret"
    litellm_url: str = "http://litellm:4000"
    litellm_master_key: str = "sk-crawlops-master-dev"
    camofox_url: str = "http://camofox:9377"
    camofox_access_key: str = ""
    camofox_api_key: str = "crawlops_camofox_cookiekey"  # enables cookie import
    loginsvc_url: str = "http://loginsvc:8500"
    rsshub_url: str = "http://rsshub:1200"
    # optional Cloudflare-challenge solver (start with --profile cloudflare); blank = off
    flaresolverr_url: str = "http://flaresolverr:8191"

    threads_access_token: str = ""
    youtube_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    admin_user: str = "admin"
    admin_password: str = "crawlops-change-me"
    secret_key: str = "crawlops-secret-change-me"  # encrypts provider API keys at rest
    # dedicated JWT signing secret — MUST be set to a random 32+ char value in prod;
    # auth fails closed if left empty/default (see services/auth.py).
    jwt_secret: str = ""
    # comma-separated allowlist of browser origins for CORS; "*" = any (dev default).
    # The browser extension has host_permissions so it bypasses CORS regardless.
    cors_origins: str = "*"

    allow_direct_stealth: bool = False
    judge_threshold_default: int = 55
    cluster_sim_news: float = 0.82
    cluster_sim_social: float = 0.78
    enrich_catchup_minutes: int = 2   # local Ollama is free; keep the backlog drained

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
