"""
Email sending module — Resend + Jinja2.

Templates live in app/templates/emails/*.html

Workflow to add a new template:
  1. Design in Beefree (or write manually).
  2. Save as app/templates/emails/<name>.html
  3. Add a send_<name>_email() function below.
  4. Add <meta name="color-scheme" content="light"> for Gmail dark mode safety.
"""

from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "emails"
_jinja = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _render(template_name: str, **kwargs: object) -> str:
    site_url = settings.frontend_url.split(",")[0].strip()
    return _jinja.get_template(template_name).render(site_url=site_url, **kwargs)


def _send(*, to: str | list[str], subject: str, html: str, reply_to: str | None = None) -> None:
    if not settings.resend_api_key:
        return
    resend.api_key = settings.resend_api_key
    payload: dict = {
        "from": f"{settings.mail_from_name} <{settings.mail_from}>",
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "html": html,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    resend.Emails.send(payload)


# ---------------------------------------------------------------------------
# Send functions — add one per email type
# ---------------------------------------------------------------------------

def send_verification_email(to: str, token: str) -> None:
    site_url = settings.frontend_url.split(",")[0].strip()
    _send(
        to=to,
        subject="Verify your email",
        html=_render("verification.html", verify_url=f"{site_url}/verify?token={token}"),
    )


def send_password_reset_email(to: str, token: str) -> None:
    site_url = settings.frontend_url.split(",")[0].strip()
    _send(
        to=to,
        subject="Reset your password",
        html=_render("password_reset.html", reset_url=f"{site_url}/reset-password?token={token}"),
    )
