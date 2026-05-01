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

**When to use:** any project where users should be able to protect their account with an authenticator app (Google Authenticator, Authy, etc.).

### Install
```
# requirements.txt
pyotp==2.9.0
qrcode[pil]==8.0
```

### Config (`config.py`)
```python
totp_issuer: str = "My App"   # shown in the authenticator app
```

---

### DB changes

**1. Add two columns to the `User` model:**
```python
totp_secret: Mapped[str | None] = mapped_column(String, nullable=True)
totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

**2. Create a separate `TotpBackupCode` table** — do NOT store backup codes as a column in `users`:
```python
# models/totp_backup_code.py
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.database import Base

class TotpBackupCode(Base):
    __tablename__ = "totp_backup_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String, nullable=False)       # bcrypt hash — never plaintext
    used_at = Column(DateTime(timezone=True), nullable=True)   # None = available
```

Import in `alembic/env.py`, then:
```bash
alembic revision --autogenerate -m "add totp columns and backup codes table"
alembic upgrade head
```

---

### Login flow with 2FA

Standard login changes to a two-step flow when `totp_enabled=True`:

1. `POST /auth/login` — validates password, returns a **partial token** (`scope: "2fa_pending"`, 5 min expiry) instead of a full access token.
2. User submits partial token + TOTP code (or backup code) to complete login.

**Partial token creation:**
```python
def create_partial_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "jti": str(uuid.uuid4()), "scope": "2fa_pending"},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
```

**Partial token validation (shared helper):**
```python
def _verify_partial_token(partial_token: str) -> str:
    """Decode a 2fa_pending token and return user_id. Raises 401 on failure."""
    try:
        payload = jwt.decode(partial_token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired 2FA session")
    if payload.get("scope") != "2fa_pending":
        raise HTTPException(status_code=401, detail="Invalid token scope")
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id
```

---

### Router — `routers/totp.py`

Five endpoints, all rate-limited:

| Endpoint | Auth required | Rate limit | Purpose |
|----------|--------------|-----------|---------|
| `POST /auth/2fa/setup` | full JWT | 10/min | Generate secret + QR code. Does NOT enable 2FA yet. |
| `POST /auth/2fa/enable` | full JWT | 10/min | Verify first TOTP code, activate 2FA, return one-time backup codes. |
| `POST /auth/2fa/verify` | partial token | 10/min | Exchange partial token + TOTP code → full access token. |
| `POST /auth/2fa/verify-backup` | partial token | **5/hour** | Exchange partial token + backup code → full access token. Consumes code. |
| `DELETE /auth/2fa/disable` | full JWT | 10/min | Disable 2FA after verifying current TOTP. Deletes all backup codes. |

**Setup:**
```python
@router.post("/setup")
@limiter.limit("10/minute")
def setup_totp(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name=current_user.email, issuer_name=settings.totp_issuer)
    current_user.totp_secret = secret   # pending — not active until /enable succeeds
    db.commit()
    return {"secret": secret, "qr_data_url": f"data:image/png;base64,{_qr_png_b64(uri)}"}
```

**Enable (returns backup codes — shown once):**
```python
_BACKUP_CODE_COUNT = 8
_BACKUP_CODE_LENGTH = 10  # hex chars

def _generate_backup_codes() -> tuple[list[str], list[str]]:
    plain = [secrets.token_hex(_BACKUP_CODE_LENGTH // 2) for _ in range(_BACKUP_CODE_COUNT)]
    hashed = [bcrypt.hashpw(c.encode(), bcrypt.gensalt()).decode() for c in plain]
    return plain, hashed

@router.post("/enable")
@limiter.limit("10/minute")
def enable_totp(request: Request, data: EnableRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Call /auth/2fa/setup first")
    if not pyotp.TOTP(current_user.totp_secret).verify(data.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    plain_codes, hashed_codes = _generate_backup_codes()
    db.query(TotpBackupCode).filter(TotpBackupCode.user_id == current_user.id).delete()
    for code_hash in hashed_codes:
        db.add(TotpBackupCode(user_id=current_user.id, code_hash=code_hash))
    current_user.totp_enabled = True
    db.commit()
    return {"backup_codes": plain_codes}   # show once — user must save these
```

**Verify with backup code (single-use, strict rate limit):**
```python
def _verify_and_consume_backup_code(user_id: str, code: str, db: Session) -> bool:
    rows = db.query(TotpBackupCode).filter(
        TotpBackupCode.user_id == user_id,
        TotpBackupCode.used_at.is_(None)
    ).all()
    for row in rows:
        if bcrypt.checkpw(code.encode(), row.code_hash.encode()):
            row.used_at = datetime.now(timezone.utc)
            db.commit()
            return True
    return False

@router.post("/verify-backup")
@limiter.limit("5/hour")    # strict — brute force protection
def verify_backup_code(request: Request, data: VerifyBackupRequest, db: Session = Depends(get_db)):
    user_id = _verify_partial_token(data.partial_token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.totp_enabled:
        raise HTTPException(status_code=401, detail="Invalid 2FA session")
    if not _verify_and_consume_backup_code(user_id, data.code.strip(), db):
        raise HTTPException(status_code=400, detail="Invalid or already used backup code")
    return Token(access_token=create_access_token(str(user.id)))
```

**Disable (verifies current TOTP, wipes all backup codes):**
```python
@router.delete("/disable", status_code=204)
@limiter.limit("10/minute")
def disable_totp(request: Request, data: DisableRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.totp_enabled or not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    if not pyotp.TOTP(current_user.totp_secret).verify(data.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid verification code")
    db.query(TotpBackupCode).filter(TotpBackupCode.user_id == current_user.id).delete()
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.commit()
```

---

### Security design

- **Backup codes stored hashed** — bcrypt per code, same security as passwords. Never store plaintext.
- **Shown exactly once** — `/enable` response. Not retrievable after that.
- **Single-use** — `used_at` is set on consumption; subsequent checks skip used rows.
- **Separate table** — `totp_backup_codes` with `CASCADE` delete. Clean deletion when 2FA disabled or user deleted.
- **Strict rate limit on `/verify-backup`** — 5/hour vs 10/min on TOTP. Backup codes have no time rotation, so brute force protection is critical.
- **Partial token scope** — `"scope": "2fa_pending"` prevents reuse of the intermediate token for anything other than completing 2FA.

### Reference files
- `backend/app/routers/totp.py` — full router implementation
- `backend/app/models/totp_backup_code.py` — backup codes model

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
