"""Tests for CloudflareOnlyMiddleware — shared-secret validation.

Regression coverage for a production incident: the middleware used to check
request.client.host against Cloudflare's published IP ranges, which only
works when Cloudflare connects directly to the origin. On platforms where a
proxy sits in between (e.g. Railway), the raw TCP peer is the platform's own
internal proxy — never Cloudflare's edge IP — so that check blocked 100% of
requests, including login, whenever CLOUDFLARE_ONLY=true was set.

A presence-only check of CF-Connecting-IP is equally wrong in the other
direction: anyone hitting the origin directly can set that header themselves.
"""

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import CloudflareOnlyMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(CloudflareOnlyMiddleware)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/v1/auth/login")
    def login():
        return {"ok": True}

    @app.post("/webhooks/stripe")
    def webhook():
        return {"ok": True}

    return TestClient(app)


class TestCloudflareOnlyMiddleware:
    def test_disabled_allows_all_requests(self):
        with patch("app.main.settings.cloudflare_only", False):
            res = _client().get("/v1/auth/login")
        assert res.status_code == 200

    def test_health_always_allowed_even_when_enabled(self):
        with (
            patch("app.main.settings.cloudflare_only", True),
            patch("app.main.settings.cloudflare_shared_secret", "s3cr3t"),
        ):
            res = _client().get("/health")
        assert res.status_code == 200

    def test_webhooks_bypass_shared_secret(self):
        # Third-party webhook callers can't send the Transform-Rule header;
        # they authenticate via their own signature (Stripe, Svix, etc.).
        with (
            patch("app.main.settings.cloudflare_only", True),
            patch("app.main.settings.cloudflare_shared_secret", "s3cr3t"),
        ):
            res = _client().post("/webhooks/stripe")
        assert res.status_code == 200

    def test_enabled_blocks_missing_header(self):
        with (
            patch("app.main.settings.cloudflare_only", True),
            patch("app.main.settings.cloudflare_shared_secret", "s3cr3t"),
        ):
            res = _client().get("/v1/auth/login")
        assert res.status_code == 403

    def test_enabled_blocks_wrong_secret(self):
        with (
            patch("app.main.settings.cloudflare_only", True),
            patch("app.main.settings.cloudflare_shared_secret", "s3cr3t"),
        ):
            res = _client().get("/v1/auth/login", headers={"X-Origin-Auth": "wrong"})
        assert res.status_code == 403

    def test_enabled_blocks_spoofed_cf_connecting_ip(self):
        # Regression guard against the old presence-only check: a forged
        # CF-Connecting-IP header without the shared secret must NOT pass.
        with (
            patch("app.main.settings.cloudflare_only", True),
            patch("app.main.settings.cloudflare_shared_secret", "s3cr3t"),
        ):
            res = _client().get(
                "/v1/auth/login", headers={"CF-Connecting-IP": "1.2.3.4"}
            )
        assert res.status_code == 403

    def test_enabled_allows_correct_secret(self):
        with (
            patch("app.main.settings.cloudflare_only", True),
            patch("app.main.settings.cloudflare_shared_secret", "s3cr3t"),
        ):
            res = _client().get("/v1/auth/login", headers={"X-Origin-Auth": "s3cr3t"})
        assert res.status_code == 200

    def test_does_not_check_client_host_at_all(self):
        # Regression guard: a request whose TCP peer is a private/CGNAT address
        # (as Railway's internal proxy always presents) must still succeed as
        # long as the shared secret header is correct — this is the exact
        # scenario that broke production.
        with (
            patch("app.main.settings.cloudflare_only", True),
            patch("app.main.settings.cloudflare_shared_secret", "s3cr3t"),
        ):
            res = _client().get(
                "/v1/auth/login",
                headers={"X-Origin-Auth": "s3cr3t"},
            )
        assert res.status_code == 200
