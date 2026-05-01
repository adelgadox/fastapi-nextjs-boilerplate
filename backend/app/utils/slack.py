"""
Slack Bot notifications via chat.postMessage.

Usage:
    from app.utils.slack import notify_slack
    await notify_slack("Hello!", channel="#backend-alerts")

The bot must be invited to each channel before it can post:
    /invite @BotName

Requires SLACK_BOT_TOKEN (xoxb-...) in environment.
All failures are silently swallowed — Slack never blocks a user request.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_SLACK_API = "https://slack.com/api/chat.postMessage"


async def notify_slack(text: str, channel: str) -> None:
    """Post a message to a Slack channel via the bot.

    No-op when SLACK_BOT_TOKEN is not configured.
    Never raises — failures are logged as warnings only.
    """
    if not settings.slack_bot_token:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                _SLACK_API,
                headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
                json={"channel": channel, "text": text},
            )
    except Exception as exc:
        logger.warning("Slack notification failed (channel=%s): %s", channel, exc)
