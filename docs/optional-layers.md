# Optional Layers

Each layer is **off by default**. Enable only what your project needs.
Steps: uncomment the package in `requirements.txt`, uncomment the settings in `config.py`, set env vars, implement.

---

## Cloudinary — Image / Video Uploads

**When to use:** profile photos, cover images, user-uploaded media.

### Install
```
# requirements.txt
cloudinary==1.41.0
```

### Env vars
```
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

### Usage pattern
```python
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
)

result = cloudinary.uploader.upload(file_bytes, folder="avatars", public_id=user_id)
url = result["secure_url"]
```

### Notes
- Upload from FastAPI endpoint, store `secure_url` in user model
- Use `transformation` parameter for resizing on upload (avoid storing originals)
- Free plan: 25 GB storage + 25 GB bandwidth/month

---

## AI / OpenAI-compatible Provider

**When to use:** chat, completions, embeddings, structured output.
**Compatible providers:** OpenAI, DeepSeek, Groq, Together AI, Mistral, Ollama (local).

### Install
```
# requirements.txt
openai==1.55.0
```

### Config (`config.py`)
```python
ai_api_key: str = ""
ai_base_url: str = "https://api.openai.com/v1"
ai_model: str = "gpt-4o-mini"
```

### Env vars
```
AI_API_KEY=sk-...
AI_BASE_URL=https://api.openai.com/v1        # or https://api.deepseek.com/v1
AI_MODEL=gpt-4o-mini                         # or deepseek-chat
```

### Usage pattern
```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=settings.ai_api_key, base_url=settings.ai_base_url)

response = await client.chat.completions.create(
    model=settings.ai_model,
    messages=[{"role": "user", "content": prompt}],
)
text = response.choices[0].message.content
```

### Notes
- `base_url` swap = provider swap, no code changes
- DeepSeek: `https://api.deepseek.com/v1`, model `deepseek-chat`
- Groq: `https://api.groq.com/openai/v1`, model `llama-3.1-8b-instant`

---

## Langfuse — LLM Observability

**When to use:** trace LLM calls, evaluate responses, manage prompts, monitor costs.

### Install
```
# requirements.txt
langfuse==2.26.0
```

### Env vars
```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com     # or self-hosted URL
```

### Usage pattern (decorator)
```python
from langfuse.decorators import observe, langfuse_context

@observe()
async def generate_response(user_id: str, prompt: str) -> str:
    langfuse_context.update_current_trace(user_id=user_id)
    response = await client.chat.completions.create(...)
    return response.choices[0].message.content
```

### Usage pattern (OpenAI integration)
```python
from langfuse.openai import AsyncOpenAI  # drop-in replacement

client = AsyncOpenAI(api_key=settings.ai_api_key, base_url=settings.ai_base_url)
# All calls are automatically traced
```

### Notes
- Free plan: 50k observations/month
- Self-host with Docker for unlimited + data privacy

---

## Stripe — Payments & Subscriptions

**When to use:** paid plans, one-time purchases, usage-based billing.

### Install
```
# requirements.txt
stripe==11.2.0
```

### Config (`config.py`)
```python
stripe_secret_key: str = ""
stripe_webhook_secret: str = ""
stripe_price_id_pro: str = ""
```

### Env vars
```
STRIPE_SECRET_KEY=sk_live_...          # sk_test_... for development
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PRO=price_...
```

### Router pattern
```python
import stripe
stripe.api_key = settings.stripe_secret_key

# Create checkout session
@router.post("/billing/checkout")
async def create_checkout(current_user: User = Depends(get_current_user)):
    session = stripe.checkout.Session.create(
        customer_email=current_user.email,
        line_items=[{"price": settings.stripe_price_id_pro, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.frontend_url.split(',')[0].strip()}/dashboard?upgraded=1",
        cancel_url=f"{settings.frontend_url.split(',')[0].strip()}/dashboard",
        metadata={"user_id": str(current_user.id)},
    )
    return {"url": session.url}

# Webhook handler
@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    if event["type"] == "checkout.session.completed":
        # upgrade user plan in DB
        ...
    return {"ok": True}
```

### Notes
- Always verify webhook signature (prevents spoofing)
- Use Railway Cron or Stripe billing portal for subscription management
- Test with `stripe listen --forward-to localhost:8000/billing/webhook`

---

## Redis — Caching & Queues

**When to use:** cache expensive queries, rate limiting store, background task queues, batched counters.

### Install
```
# requirements.txt
redis==5.2.1
```

### Config (`config.py`)
```python
# Redis (optional — degrades gracefully when absent)
# Railway injects REDIS_URL automatically when the Redis addon is added.
redis_url: str = ""
```

### Env vars
```
REDIS_URL=redis://localhost:6379/0      # or rediss://... for TLS
```

### Graceful degradation pattern (recommended)

Design Redis as optional: when `REDIS_URL` is unset or Redis is down, the app falls back to the DB path without crashing.

```python
# utils/cache.py
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_client = None
_unavailable = False  # once confirmed down, skip further attempts


def _get_client():
    global _client, _unavailable
    if _unavailable:
        return None
    if _client is not None:
        return _client
    url = os.environ.get("REDIS_URL", "")
    if not url:
        _unavailable = True
        return None
    try:
        import redis as redis_lib
        _client = redis_lib.from_url(url, decode_responses=True, socket_timeout=0.5)
        _client.ping()
        logger.info("Redis connected (%s)", url.split("@")[-1])
    except Exception:
        logger.warning("Redis unavailable — cache disabled")
        _client = None
        _unavailable = True
    return _client


def get_cached(key: str) -> Optional[str]:
    r = _get_client()
    if r is None:
        return None
    try:
        return r.get(key)
    except Exception:
        return None


def set_cached(key: str, value: str, ttl: int = 300) -> None:
    r = _get_client()
    if r is None:
        return
    try:
        r.setex(key, ttl, value)
    except Exception:
        pass


def invalidate(key: str) -> None:
    r = _get_client()
    if r is None:
        return
    try:
        r.delete(key)
    except Exception:
        pass
```

### Batched counter pattern (high-traffic writes)

Useful for click/view counters: accumulate in Redis, flush to DB every N hits.

```python
_FLUSH_EVERY = 50

def increment_counter(entity_id: str) -> Optional[int]:
    """Returns new count, or None if Redis unavailable (caller writes to DB directly)."""
    r = _get_client()
    if r is None:
        return None
    try:
        return r.incr(f"counter:{entity_id}")
    except Exception:
        return None

def pop_counter(entity_id: str) -> int:
    """Atomically read and reset counter. Returns 0 if Redis unavailable."""
    r = _get_client()
    if r is None:
        return 0
    try:
        pipe = r.pipeline()
        pipe.getdel(f"counter:{entity_id}")
        raw = pipe.execute()[0]
        return int(raw) if raw else 0
    except Exception:
        return 0

def should_flush(count: Optional[int]) -> bool:
    return count is not None and count >= _FLUSH_EVERY
```

### Local docker-compose
```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
```

### Railway setup

1. Open your Railway project → **New** → **Database** → **Add Redis**
2. Railway injects `REDIS_URL` automatically into all services in the project — no manual env var needed.
3. The URL format is `redis://default:<password>@<host>:<port>` (no TLS on internal network).
4. For TLS (external connections): use `rediss://` scheme and the public URL from Railway → Redis → Connect.

### Notes
- `socket_timeout=0.5` — fail fast on Redis issues, don't block requests
- Never store sensitive data (tokens, PII) in Redis without encryption
- Redis on Railway is **ephemeral** by default — don't use as primary data store

---

## PgBouncer — Connection Pooling

**When to use:** Railway (or any PaaS) where each app instance opens its own DB connections. Prevents exhausting PostgreSQL's connection limit under load.

**Why:** PostgreSQL handles ~100 concurrent connections by default. Without pooling, multiple app replicas + Alembic migrations can exhaust this limit, causing `too many connections` errors.

### How it works

PgBouncer sits between FastAPI and PostgreSQL, multiplexing many app connections into a small pool of real DB connections. In **transaction mode**, a server connection is only held for the duration of a transaction, then returned to the pool.

### SQLAlchemy changes (already in `database.py`)

`PGBOUNCER_MODE=true` switches to `NullPool` + disables prepared statements:

```python
# database.py (already implemented — just set the env var)
if settings.pgbouncer_mode:
    engine = create_engine(
        settings.database_url,
        poolclass=NullPool,            # PgBouncer manages the pool, not SQLAlchemy
        connect_args={"prepare_threshold": None},  # prepared statements incompatible with transaction mode
    )
```

### Railway setup

**1. Add a new Railway service** using image `edoburu/pgbouncer:latest`

> Do NOT use `bitnami/pgbouncer` — removed from Docker Hub after Broadcom acquisition.

**2. Set these env vars on the pgbouncer service:**

| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgres://postgres:<password>@<tcp-proxy-host>:<tcp-proxy-port>/railway` |
| `DATABASES_HOST` | `<tcp-proxy-host>` (e.g. `gondola.proxy.rlwy.net`) — **host only, no port** |
| `DATABASES_PORT` | `<tcp-proxy-port>` (e.g. `27789`) |
| `DATABASES_USER` | `postgres` |
| `DATABASES_PASSWORD` | your Postgres password |
| `DATABASES_DBNAME` | `railway` |
| `POOL_MODE` | `transaction` |
| `MAX_CLIENT_CONN` | `100` |
| `DEFAULT_POOL_SIZE` | `20` |

> **Critical:** `DATABASES_HOST` must be the hostname **without** the port. If you put `host:port` in `DATABASES_HOST`, PgBouncer treats the whole string as the hostname and DNS resolution fails.

> **Why the public TCP proxy?** PgBouncer runs as a Docker container — Railway's private network (`postgres.railway.internal`) is only reachable by Railway-native services. Use the TCP proxy host from Railway → Postgres → Connect → Public URL.

**3. Get PgBouncer's private domain:**

Railway → pgbouncer service → Settings → Networking → Private Domain
(e.g. `pgbouncer.railway.internal`, port `6432`)

**4. Update FastAPI env vars:**

```
DATABASE_URL=postgresql://postgres:<password>@pgbouncer.railway.internal:6432/railway
PGBOUNCER_MODE=true
```

**5. Verify it's working** — in Railway → pgbouncer service logs you should see:
```
LOG listening on 0.0.0.0:6432
LOG S-0x...: railway/postgres@<ip>:<port> new connection to server
```

The second line confirms PgBouncer connected to Postgres successfully.

### Notes
- `PGBOUNCER_MODE=false` (default) — standard SQLAlchemy pool, fine for single-instance local/staging
- `PGBOUNCER_MODE=true` — production Railway deployments with multiple replicas
- Alembic migrations must run **before** switching to PgBouncer URL (prepared statements are used during migration)

---

## 2FA / TOTP — Authenticator App Codes

**When to use:** admin / superadmin accounts, high-security user actions.

### Install
```
# requirements.txt
pyotp==2.9.0
qrcode[pil]==8.0
```

### Config (`config.py`)
```python
totp_issuer: str = "My App"
```

### DB columns (add to User model)
```python
totp_secret: str | None = None       # encrypted at rest recommended
totp_enabled: bool = False
totp_backup_codes: list[str] = []    # bcrypt-hashed, never plaintext
```

### Usage pattern
```python
import pyotp, qrcode, io, base64

def generate_totp_secret() -> str:
    return pyotp.random_base32()

def get_totp_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=email, issuer_name=settings.totp_issuer
    )

def get_qr_base64(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)
```

### Backup codes
```python
import secrets, bcrypt

def generate_backup_codes(n: int = 10) -> tuple[list[str], list[str]]:
    """Returns (plaintext_to_show_once, hashed_to_store)."""
    codes = [secrets.token_hex(5) for _ in range(n)]
    hashed = [bcrypt.hashpw(c.encode(), bcrypt.gensalt()).decode() for c in codes]
    return codes, hashed

def verify_backup_code(code: str, hashed_codes: list[str]) -> int | None:
    """Returns index of matched code, or None. Caller must delete used code."""
    for i, h in enumerate(hashed_codes):
        if bcrypt.checkpw(code.encode(), h.encode()):
            return i
    return None
```

### Notes
- **Never store backup codes in plaintext** — hash with bcrypt same as passwords
- Show plaintext codes exactly once (on setup screen), then discard
- Rate-limit backup code endpoint (3 attempts / hour)
- Store `totp_secret` encrypted in DB for defense in depth

---

## GeoIP / MaxMind — Country & City Lookup

**When to use:** geo-based access control, analytics, fraud detection, localization.

### Install
```
# requirements.txt
geoip2==4.8.0
```

### Config (`config.py`)
```python
geoip_db_path: str = "/data/GeoLite2-City.mmdb"
```

### Env vars
```
GEOIP_DB_PATH=/data/GeoLite2-City.mmdb
```

### Setup
1. Create free account at [maxmind.com](https://www.maxmind.com)
2. Download `GeoLite2-City.mmdb`
3. Mount as volume in Railway / Docker

### Usage pattern
```python
import geoip2.database

_reader: geoip2.database.Reader | None = None

def get_geoip_reader() -> geoip2.database.Reader | None:
    global _reader
    if _reader is None and settings.geoip_db_path:
        _reader = geoip2.database.Reader(settings.geoip_db_path)
    return _reader

def lookup_ip(ip: str) -> dict:
    reader = get_geoip_reader()
    if not reader:
        return {}
    try:
        record = reader.city(ip)
        return {
            "country": record.country.iso_code,
            "city": record.city.name,
            "latitude": record.location.latitude,
            "longitude": record.location.longitude,
        }
    except Exception:
        return {}
```

### Notes
- `GeoLite2-City.mmdb` ≈ 70 MB — mount as volume, not in image
- Update DB monthly (MaxMind updates weekly)
- Use `get_client_ip(request)` from `utils/cloudflare.py` for the IP

---

## ElevenLabs + Cloudflare R2 — AI Voice Generation

**When to use:** AI-generated voiceovers, text-to-speech, audio content.

### Install
```
# requirements.txt
elevenlabs==1.9.0
boto3==1.35.95        # S3-compatible client for R2
```

### Config (`config.py`)
```python
elevenlabs_api_key: str = ""
elevenlabs_voice_id: str = ""
r2_account_id: str = ""
r2_access_key_id: str = ""
r2_secret_access_key: str = ""
r2_bucket_name: str = ""
r2_public_url: str = ""   # e.g. https://pub-xxx.r2.dev
```

### Env vars
```
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_URL=https://pub-xxx.r2.dev
```

### Usage pattern
```python
import boto3, uuid
from elevenlabs.client import ElevenLabs

def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )

async def generate_and_store_audio(text: str) -> str:
    client = ElevenLabs(api_key=settings.elevenlabs_api_key)
    audio = client.generate(
        text=text,
        voice=settings.elevenlabs_voice_id,
        model="eleven_multilingual_v2",
    )
    audio_bytes = b"".join(audio)
    key = f"audio/{uuid.uuid4()}.mp3"
    get_r2_client().put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=audio_bytes,
        ContentType="audio/mpeg",
    )
    return f"{settings.r2_public_url}/{key}"
```

### Notes
- Add `media-src blob: https://pub-xxx.r2.dev` to CSP header in `main.py`
- R2 free tier: 10 GB storage + 1M Class A ops/month (no egress fees)
- ElevenLabs free tier: 10k characters/month
- Stream audio directly from R2 public URL — no proxying needed
