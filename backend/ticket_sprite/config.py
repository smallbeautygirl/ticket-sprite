"""Runtime settings, read from environment variables (prefix-free) or `.env`."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./ticket_sprite.db"
    public_base_url: str = "http://localhost:3000"

    # --- login (ADR-0001) ---
    auth_mode: Literal["observ", "dev"] = "observ"
    observ_base_url: str = "https://lighthouse-production.visionai.linkervision.ai/observ"
    observ_service_id: str = "e39940ea-1fdf-4527-a3b7-c8d6334e5d2e"
    session_secret: str = "change-me"
    session_max_age_seconds: int = 60 * 60 * 24 * 7
    allowed_emails: str = ""  # comma-separated trial allowlist; empty = anyone who can log in to Observ

    # --- ADO ---
    ado_org: str = "linkerengineer"
    ado_project: str = "Deliver team"
    ado_area_path: str = "Deliver team"
    ado_default_parent_id: int = 41152
    fernet_key: str = ""  # Fernet key for encrypting PATs; required outside tests
    ado_dev_pat: str = ""  # dev only: shared PAT used when a user has none

    # --- Claude ---
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    llm_mode: Literal["claude", "claude_code", "fake"] = "claude"
    # claude_code: run the owner's own `claude -p` (their Claude login). Single-user only.
    claude_code_bin: str = "claude"
    claude_code_model: str = ""  # empty = the CLI's default model
    claude_code_timeout_seconds: int = 900
    owner_email: str = ""  # the only account allowed to log in when single_user

    # --- Knowledge Source (ADR-0002) ---
    knowledge_root: Path = Path("./knowledge")
    knowledge_repo_source: str = "/opt/lighthouse-saas-api"
    knowledge_repo_dir: str = "lighthouse-saas-api"
    knowledge_branch: str = "main"
    knowledge_product_subdir: str = "apps/visionai_middleware"
    knowledge_pull_interval_seconds: int = 3600

    # --- attachments ---
    upload_dir: Path = Path("./uploads")
    max_upload_bytes: int = 20 * 1024 * 1024

    # --- Teams ---
    teams_webhook_url: str = ""
    handoff_reminder_working_days: int = 2
    handoff_max_reminders: int = 2
    reminder_check_interval_seconds: int = 1800

    @property
    def allowlist(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_emails.split(",") if e.strip()}

    def may_log_in(self, email: str) -> bool:
        email = email.strip().lower()
        if self.single_user:
            return email == self.owner_email.strip().lower()
        return not self.allowlist or email in self.allowlist

    @property
    def single_user(self) -> bool:
        """The owner's personal Claude login may only serve the owner."""
        return self.llm_mode == "claude_code"

    @property
    def product_root(self) -> Path:
        return self.knowledge_root / self.knowledge_repo_dir / self.knowledge_product_subdir


@lru_cache
def get_settings() -> Settings:
    return Settings()
