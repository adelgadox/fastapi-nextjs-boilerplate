from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "My App API"
    debug: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str
    pgbouncer_mode: bool = False

    # ── JWT ───────────────────────────────────────────────────────────────────
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins (multi-origin CORS support)
    # When building URLs for emails, always use: frontend_url.split(",")[0].strip()
    frontend_url: str = "http://localhost:3000"

    # ── Internal API secret ───────────────────────────────────────────────────
    # Shared between Next.js server actions and FastAPI to protect
    # server-to-server endpoints (e.g. POST /internal/*) from public access
    internal_api_secret: str = ""

    # ── Email — Resend ────────────────────────────────────────────────────────
    resend_api_key: str = ""
    mail_from: str = "noreply@yourdomain.com"
    mail_from_name: str = "My App"

    # ── Trusted proxy IPs ─────────────────────────────────────────────────────
    # Set to "*" on Railway (all traffic passes through Railway's proxy)
    trusted_proxy_ips: str = "127.0.0.1"

    # ── Sentry (optional — error tracking disabled when absent) ───────────────
    sentry_dsn: str = ""
    sentry_environment: str = "production"

    # ── Slack Bot (optional — notifications disabled when absent) ─────────────
    # Bot Token from api.slack.com → Your App → OAuth & Permissions (xoxb-...)
    # One token covers all channels; invite bot to each channel with /invite @bot
    slack_bot_token: str = ""

    # ── OAuth — Google (optional) ─────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""

    # =========================================================================
    # OPTIONAL LAYERS — uncomment + set env vars to activate
    # See docs/optional-layers.md for full setup instructions
    # =========================================================================

    # ── Cloudinary (optional — image / video uploads) ─────────────────────────
    # pip install cloudinary==1.41.0
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # ── AI / OpenAI-compatible (optional — LLM features) ─────────────────────
    # pip install openai==1.55.0
    # Works with OpenAI, DeepSeek, Groq, Together AI, etc. via base_url
    # ai_api_key: str = ""
    # ai_base_url: str = "https://api.openai.com/v1"   # override for other providers
    # ai_model: str = "gpt-4o-mini"

    # ── Langfuse (optional — LLM observability) ───────────────────────────────
    # pip install langfuse==2.26.0
    # langfuse_public_key: str = ""
    # langfuse_secret_key: str = ""
    # langfuse_host: str = "https://cloud.langfuse.com"

    # ── Stripe (optional — payments & subscriptions) ──────────────────────────
    # pip install stripe==11.2.0
    # stripe_secret_key: str = ""
    # stripe_webhook_secret: str = ""
    # stripe_price_id_pro: str = ""   # add one per plan

    # ── Redis (optional — caching, queues) ────────────────────────────────────
    # pip install redis==5.2.1
    # redis_url: str = "redis://localhost:6379/0"

    # ── 2FA / TOTP (optional — authenticator apps) ────────────────────────────
    # pip install pyotp==2.9.0 qrcode[pil]==8.0
    # totp_issuer: str = "My App"

    # ── GeoIP / MaxMind (optional — country / city lookup) ───────────────────
    # pip install geoip2==4.8.0
    # Download GeoLite2-City.mmdb from maxmind.com (free account required)
    # geoip_db_path: str = "/data/GeoLite2-City.mmdb"

    # ── ElevenLabs + R2 (optional — AI voice generation + storage) ────────────
    # pip install elevenlabs==1.9.0 boto3==1.35.95
    # elevenlabs_api_key: str = ""
    # elevenlabs_voice_id: str = ""
    # r2_account_id: str = ""
    # r2_access_key_id: str = ""
    # r2_secret_access_key: str = ""
    # r2_bucket_name: str = ""
    # r2_public_url: str = ""   # e.g. https://pub-xxx.r2.dev

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
