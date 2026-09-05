from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api"

    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    QR_CODE_BASE_URL: str = "http://localhost:5173"
    """Frontend origin encoded into asset QR codes (brief §6.3) — scanning
    opens the asset profile there, e.g. {QR_CODE_BASE_URL}/assets/<asset_tag>."""

    BOOTSTRAP_ADMIN_EMAIL: str = "admin@statistics.gov.sl"
    BOOTSTRAP_ADMIN_PASSWORD: str = "change-me-immediately"

    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_BUCKET: str | None = None
    S3_REGION: str = "us-east-1"

    # Login lockout policy (§15: login attempt monitoring)
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    # --- Email notifications (brief §12: event-driven, must never block a
    # core logistics transaction if the mail service is unavailable — sending
    # happens via a queued Celery task, never inline in a request). Credentials
    # live only here (env vars), never in the DB or an API response (§15). ---
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 465
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_SSL: bool = True
    """True for implicit-TLS ports like 465; set False + rely on STARTTLS for 587."""
    EMAIL_FROM_ADDRESS: str | None = None
    EMAIL_FROM_NAME: str = "SLPHC 2026 Logistics"

    # Stored for a future two-way mail feature (bounce/reply handling) — not
    # used by anything yet.
    IMAP_HOST: str | None = None
    IMAP_PORT: int = 993

    @property
    def email_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USERNAME and self.SMTP_PASSWORD)

    # --- SMS notifications (AppHiveSL gateway, api.sierrahive.com, brief §12).
    # Same never-block-a-transaction rule as email: sending happens via a
    # queued Celery task, never inline in a request. ---
    SMS_API_BASE_URL: str = "https://api.sierrahive.com"
    SMS_CLIENT_ID: str | None = None
    SMS_CLIENT_SECRET: str | None = None
    SMS_TOKEN: str | None = None
    """Sent as the `X-Wallet: Token <value>` header on every send — separate
    from CLIENT_ID/CLIENT_SECRET, which form the HTTP Basic Authorization
    header per AppHiveSL's API docs."""
    SMS_SENDER_ID: str = "STATS SL"
    """The "From" shown to recipients — AppHiveSL caps this at 11 characters."""

    # AppHiveSL portal (human) login — not used by the API itself (the API
    # authenticates with CLIENT_ID/CLIENT_SECRET/TOKEN above), kept only so
    # the credential is on record in one place rather than lost after setup.
    SMS_PORTAL_USERNAME: str | None = None
    SMS_PORTAL_PASSWORD: str | None = None

    @property
    def sms_enabled(self) -> bool:
        return bool(self.SMS_CLIENT_ID and self.SMS_CLIENT_SECRET and self.SMS_TOKEN)


settings = Settings()
