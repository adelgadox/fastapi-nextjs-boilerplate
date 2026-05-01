from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "My App API"
    debug: bool = False

    # Database
    database_url: str
    pgbouncer_mode: bool = False

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # OAuth (optional)
    google_client_id: str = ""
    google_client_secret: str = ""

    # CORS
    frontend_url: str = "http://localhost:3000"

    # Email — Resend
    resend_api_key: str = ""
    mail_from: str = "noreply@yourdomain.com"
    mail_from_name: str = "My App"

    # Cloudinary (optional — for image uploads)
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # Internal API secret — shared between Next.js server and FastAPI
    # to protect server-to-server endpoints from public access
    internal_api_secret: str = ""

    # Sentry (optional — error tracking disabled when absent)
    sentry_dsn: str = ""
    sentry_environment: str = "production"

    # Slack Bot (optional — notifications disabled when absent)
    # Bot Token from api.slack.com → Your App → OAuth & Permissions (xoxb-...)
    slack_bot_token: str = ""

    # Trusted proxy IPs for ProxyHeadersMiddleware
    # Set to "*" on Railway (all traffic passes through Railway's proxy)
    trusted_proxy_ips: str = "127.0.0.1"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
