# Decision: File & Media Storage

**Status:** Accepted · **Date:** 2026-07 · **Origin:** pet-portal, adopted as the boilerplate default.

## Decision

Two separate storage systems, chosen per data type:

| Data type | Service | Access | Why |
|-----------|---------|--------|-----|
| **Private documents** (PDFs, health records, contracts, user uploads) | **Cloudflare R2** | Signed, time-limited GET URLs; DB stores the **object key**, never a URL | S3-compatible, **zero egress fees**, private-by-default. Client fetches presigned URLs directly. |
| **Public images** (avatars, thumbnails, catalog images) | **Cloudinary** | Public CDN URL (`secure_url`), server-side signed upload | CDN delivery, on-the-fly `webp`/transform, cache/invalidate. |

## Rationale

- **R2 for documents** — private files must never be world-readable. Presigned
  URLs (TTL ~300s) mean the DB holds only the object key; access is authorized
  per request. Zero egress makes document-heavy apps cheap.
- **Cloudinary for images** — public images benefit from a transform CDN.
  Uploads go **server-side** through FastAPI using the `api_secret` (no unsigned
  browser presets — that was a real finding in bioflow Phase 15 · M5).

## Implementation pattern (see roadmap phase-02)

- **`StoragePort`** ABC (`upload` / `delete` / `signed_url`) with an **`R2Adapter`**
  (boto3, `signature_version="s3v4"`) — injected via `Depends(get_storage)` so a
  `FakeStorage` swaps in for tests (offline signing, no network).
- **Upload validation**: type allowlist + size cap + **magic-byte sniffing**
  (don't trust `Content-Type`).
- **Ownership**: object keys namespaced by owner (`entity/{id}/docs/{uuid}.{ext}`)
  and backed by an RLS policy (roadmap phase-03).
- **GDPR**: `purge_object_keys_for_user` wipes a user's R2 objects on account
  deletion (roadmap phase-07).

## Env vars

```
# Cloudflare R2 (documents)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=

# Cloudinary (images)
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

## Alternatives considered

- **Single provider for both** — rejected: no one service is best at both
  private object storage *and* an image-transform CDN.
- **AWS S3** — rejected for documents: R2's zero egress is materially cheaper for
  download-heavy workloads; S3-compatible API means the `R2Adapter` is portable if that changes.
- **Direct browser→Cloudinary unsigned upload** — rejected: bypasses server-side
  validation and leaks upload capability to the client.
