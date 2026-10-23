from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://scraper:scraper_pass@localhost:5432/scraper_db"
    # Synchronous driver, used by the Streamlit app, the web API and CLI scripts.
    database_url_sync: str = "postgresql+psycopg2://scraper:scraper_pass@localhost:5432/scraper_db"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # LinkedIn
    linkedin_username: str = ""
    linkedin_password: str = ""

    # SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # Prefect
    prefect_api_url: str = "http://localhost:4200/api"

    # App
    log_level: str = "INFO"
    log_format: str = "json"
    jobs_config_path: str = "config/jobs.yaml"

    # Runtime files the app writes. All live under runtime/ (git-ignored, one Docker volume).
    auth_state_path: str = "runtime/data/auth_state.json"
    # Candidate resumes; stored paths are relative to this directory.
    resume_upload_dir: str = "runtime/resumes"
    log_dir: str = "runtime/logs"
    extract_dir: str = "runtime/extract"
    debug_dir: str = "runtime/debug"

    # Web app (apps/web + gt_linkedin_scraper.web)
    # Signs session tokens. If empty, a random key is generated and sessions end on restart.
    web_secret_key: str = ""
    web_token_ttl: int = 12 * 3600
    web_invite_ttl_days: int = 7
    # Base URL used in invite links; defaults to the URL the request came in on.
    web_public_url: str = ""
    # Built Angular app served by the web API (empty = API only).
    web_static_dir: str = "apps/web/dist/web/browser"

    # Tag recipients (comma-separated env vars)
    tag_recipients__devops: str = ""
    tag_recipients__java: str = ""
    tag_recipients__qa: str = ""
    tag_recipients__freshers: str = ""
    tag_recipients__data_engineer: str = ""
    tag_recipients__default: str = "epostgauravtalele@gmail.com"

    @property
    def tag_recipients_map(self) -> dict[str, list[str]]:
        raw = {
            "devops": self.tag_recipients__devops,
            "java": self.tag_recipients__java,
            "qa": self.tag_recipients__qa,
            "freshers": self.tag_recipients__freshers,
            "data_engineer": self.tag_recipients__data_engineer,
        }
        result = {}
        for tag, csv in raw.items():
            emails = [e.strip() for e in csv.split(",") if e.strip()]
            if emails:
                result[tag] = emails
        return result

    @property
    def all_recipients(self) -> list[str]:
        all_emails = set()
        for emails in self.tag_recipients_map.values():
            all_emails.update(emails)
        default = [e.strip() for e in self.tag_recipients__default.split(",") if e.strip()]
        all_emails.update(default)
        return list(all_emails)


settings = Settings()
