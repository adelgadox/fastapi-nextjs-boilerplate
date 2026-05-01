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

**When to use:** session store, cache expensive queries, rate limiting store, background task queues.

### Install
```
# requirements.txt
redis==5.2.1
```

### Config (`config.py`)
```python
redis_url: str = "redis://localhost:6379/0"
```

### Env vars
```
REDIS_URL=redis://localhost:6379/0      # or rediss://... for TLS
```

### Usage pattern
```python
import redis.asyncio as aioredis

# In main.py lifespan:
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    yield
    await app.state.redis.aclose()

# In route:
async def get_cached(key: str, request: Request):
    cached = await request.app.state.redis.get(key)
    if cached:
        return json.loads(cached)
    data = await compute_expensive_thing()
    await request.app.state.redis.setex(key, 300, json.dumps(data))  # TTL 5min
    return data
```

### docker-compose addition
```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
```

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
