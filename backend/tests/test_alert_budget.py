"""Noise budget for alerts.

These tests pin the module's two decisions:

- **Grouping is by problem identity**, not by text or severity. Same endpoint
  and same exception is the same problem; another endpoint sounds separately.
- **Fails open.** Without Redis there's nowhere to remember what was sent, so
  everything is sent. Between a noisy channel and a mute one, the noisy one
  gets fixed by reading it; the mute one isn't noticed until it's too late.
"""

from unittest.mock import MagicMock, patch

from app.utils.alert_budget import DEFAULT_WINDOW_SECONDS, should_send


def _redis(first_call: bool = True):
    client = MagicMock()
    client.set.return_value = first_call
    return client


def test_first_occurrence_is_sent():
    with patch("app.utils.cache.get_redis_client", return_value=_redis(True)):
        assert should_send("cron:purge_expired_tokens_cron:TimeoutError") is True


def test_repetition_within_the_window_is_silenced():
    with patch("app.utils.cache.get_redis_client", return_value=_redis(False)):
        assert should_send("cron:purge_expired_tokens_cron:TimeoutError") is False


def test_the_key_reserves_the_window_atomically():
    """SET NX and not GET + SET: two workers failing at once send one alert.

    With separate read and write there'd be a race exactly when the noise
    is loudest.
    """
    client = _redis(True)
    with patch("app.utils.cache.get_redis_client", return_value=client):
        should_send("job:send_verification_email_task:SMTPError")

    _, kwargs = client.set.call_args
    assert kwargs["nx"] is True
    assert kwargs["ex"] == DEFAULT_WINDOW_SECONDS


def test_the_window_is_configurable_per_call():
    client = _redis(True)
    with patch("app.utils.cache.get_redis_client", return_value=client):
        should_send("bounces:24h", window_seconds=7200)

    assert client.set.call_args.kwargs["ex"] == 7200


def test_without_redis_every_alert_goes_through():
    """Nowhere to remember means send everything: failing closed would mute the channel."""
    with patch("app.utils.cache.get_redis_client", return_value=None):
        assert should_send("cron:whatever:RuntimeError") is True
        assert should_send("cron:whatever:RuntimeError") is True


def test_a_broken_redis_does_not_swallow_the_alert():
    client = MagicMock()
    client.set.side_effect = RuntimeError("connection reset")
    with patch("app.utils.cache.get_redis_client", return_value=client):
        assert should_send("cron:whatever:RuntimeError") is True
