# Phase 02 — Media & File Storage

Decision (from pet-portal, 2026-07): **Cloudflare R2 for private documents**
(signed URLs, zero egress) and **Cloudinary for public images** (CDN, webp
transforms). Two deliberately separate systems. See `docs/decisions/storage.md`.

The R2 side uses a clean `StoragePort` abstraction so it's injectable and
testable offline. That port is the template to backport first.

**Legend** — Complexity: 🟢 Low · 🟡 Medium · 🔴 High · Status: ✅ Done · 🟡 Partial · ⬜ Pending

| # | Task | Description | Source | Complexity | Status |
|---|------|-------------|--------|------------|--------|
| 02.1 | `StoragePort` abstraction | ABC with `upload(key, content, content_type)`, `delete(key)`, `signed_url(key, expires_in)`. Injected via `Depends(get_storage)`. | pet-portal `core/storage/base.py` | 🟡 | ⬜ Pending |
| 02.2 | `R2Adapter` (boto3) | S3-compatible client → `https://{account}.r2.cloudflarestorage.com`, `region="auto"`, `signature_version="s3v4"`. `put_object` upload; `generate_presigned_url` for GET. Boto errors → user-safe 502. | pet-portal `core/storage/r2.py` | 🟡 | ⬜ Pending |
| 02.3 | Storage factory | `@lru_cache get_storage()` builds `R2Adapter` from settings. Env: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`. Add all four to `.env.example`. | pet-portal `core/storage/factory.py` | 🟢 | ⬜ Pending |
| 02.4 | Document service + validation | Type allowlist (`pdf, jpeg, png, webp`), `MAX_SIZE = 10 MB`, **magic-byte sniffing** (`%PDF-`, `\xff\xd8\xff`, PNG sig, `RIFF…WEBP`) to defeat content-type spoofing. Object key `entity/{id}/docs/{uuid}.{ext}`. **DB stores the object key, never a URL** — sign on demand (TTL 300s). | pet-portal `document_service.py` | 🟡 | ⬜ Pending |
| 02.5 | `FakeStorage` test double | In-memory `StoragePort` impl; `conftest` overrides `dependency_overrides[get_storage]`. Contract test asserts `R2Adapter.signed_url` signs offline (no network). | pet-portal `tests/support/fake_storage.py` | 🟢 | ⬜ Pending |
| 02.6 | Cloudinary image service | Root folder + `ALLOWED_SUBFOLDERS` allowlist, `MAX_SIZE = 5 MB`, upload via server-side `api_secret` (no unsigned browser presets), `format="webp"`, returns `secure_url`. | pet-portal `image_upload_service.py`, bioflow Phase 15 · M5 | 🟡 | ⬜ Pending |
| 02.7 | Event-loop hygiene for uploads | Wrap every `cloudinary.uploader.upload(...)` inside an async handler in `asyncio.to_thread` (blocking network call). | bioflow Phase 46 · D3 | 🟢 | ⬜ Pending |
| 02.8 | Web avatar upload endpoint | `POST /v1/profile/me/avatar` proxied server-side (retires any frontend Cloudinary signing). | bioflow Phase 46 · B5 | 🟢 | ⬜ Pending |
