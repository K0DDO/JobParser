from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://jobparser:jobparser_secret@localhost:5432/jobparser"
    redis_url: str = "redis://localhost:6379/0"
    sync_interval_minutes: int = 60
    log_level: str = "INFO"
    timezone: str = "Europe/Moscow"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    hh_access_token: str = ""
    hh_user_agent: str = "JobParserLocal/1.0 (personal; your.email@mail.ru)"
    hh_client_id: str = ""
    hh_client_secret: str = ""
    hh_redirect_uri: str = "http://localhost:8000/api/v1/auth/hh/callback"

    habr_session_cookie: str = ""
    hirify_api_key: str = ""
    talanto_api_key: str = ""
    getmatch_session_cookie: str = ""


settings = Settings()
