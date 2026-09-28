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
    rsshub_url: str = "http://rsshub:1200"

    threads_access_token: str = ""
    youtube_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    allow_direct_stealth: bool = False
    judge_threshold_default: int = 55
    cluster_sim_news: float = 0.82
    cluster_sim_social: float = 0.78
    enrich_catchup_minutes: int = 15

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
