from urllib.parse import parse_qs, urlsplit

import pytest

from app import alerts, users_store


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Isolated users.db plus SMTP enabled, with sends captured (never network)."""
    monkeypatch.setattr(users_store.settings, "cache_dir", str(tmp_path))
    users_store.reset_for_tests()
    users_store.init_users_db()

    monkeypatch.setattr(alerts.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(alerts.settings, "smtp_user", "alerts@example.com")
    monkeypatch.setattr(alerts.settings, "smtp_password", "secret")
    monkeypatch.setattr(alerts.settings, "smtp_from", "alerts@example.com")
    monkeypatch.setattr(alerts.settings, "alerts_enabled", True)
    monkeypatch.setattr(alerts.settings, "alert_max_attempts", 2)
    monkeypatch.setattr(alerts.settings, "public_site_url", "https://example.org/")

    sent: list[dict] = []

    def fake_send(to, subject, text, html=None, *, list_unsubscribe=None):
        sent.append(
            {
                "to": to,
                "subject": subject,
                "text": text,
                "html": html,
                "list_unsubscribe": list_unsubscribe,
            }
        )
        return True

    monkeypatch.setattr(alerts, "_send", fake_send)
    alerts.reset_for_tests()
    yield sent
    alerts.reset_for_tests()
    users_store.reset_for_tests()


def _subscribe(email: str, kind: str = "member_vote", bioguide_id: str = "A000055") -> None:
    users_store.subscribe_alert(email, kind, bioguide_id=bioguide_id)


def _token_from_url(url: str) -> str:
    return parse_qs(urlsplit(url).query)["token"][0]


def test_queue_alert_sends_to_active_subscribers(db):
    _subscribe("one@example.com")
    _subscribe("two@example.com", bioguide_id="B000001")

    summary = alerts.queue_alert("member_vote", "Vote on H.R. 1", "Body text")

    assert summary == {"sent": 2, "failed": 0, "skipped": 0}
    assert [m["to"] for m in db] == ["one@example.com", "two@example.com"]
    assert all(m["subject"] == "Vote on H.R. 1" for m in db)


def test_queue_alert_skips_inactive_subscribers(db):
    _subscribe("gone@example.com")
    users_store.unsubscribe_alert("gone@example.com", "member_vote", bioguide_id="A000055")

    summary = alerts.queue_alert("member_vote", "Subject", "Body")

    assert summary == {"sent": 0, "failed": 0, "skipped": 0}
    assert db == []


def test_queue_alert_filters_by_bioguide_id(db):
    _subscribe("a@example.com", bioguide_id="A000055")
    _subscribe("b@example.com", bioguide_id="B000001")

    summary = alerts.queue_alert("member_vote", "Subject", "Body", bioguide_id="b000001")

    assert summary["sent"] == 1
    assert db[0]["to"] == "b@example.com"


def test_dedupe_skips_second_identical_subject(db):
    _subscribe("one@example.com")

    first = alerts.queue_alert("member_vote", "Same subject", "Body")
    second = alerts.queue_alert("member_vote", "Same subject", "Body")

    assert first["sent"] == 1
    assert second == {"sent": 0, "failed": 0, "skipped": 1}
    assert len(db) == 1


def test_failure_is_retried_then_recorded(monkeypatch, db):
    _subscribe("one@example.com")
    attempts = {"n": 0}

    def flaky(*args, **kwargs):
        attempts["n"] += 1
        raise RuntimeError("smtp down")

    monkeypatch.setattr(alerts, "_send", flaky)

    summary = alerts.queue_alert("member_vote", "Subject", "Body")

    assert summary == {"sent": 0, "failed": 1, "skipped": 0}
    # alert_max_attempts is 2 in the fixture.
    assert attempts["n"] == 2
    assert users_store.was_delivered("one@example.com", "member_vote", "Subject")
    # The failure row blocks an endless retry loop on the next tick.
    assert alerts.queue_alert("member_vote", "Subject", "Body")["skipped"] == 1


def test_unsubscribe_link_is_in_every_body(db):
    _subscribe("one@example.com")

    alerts.queue_alert("member_vote", "Subject", "Body")

    body = db[0]["text"]
    assert "Unsubscribe:" in body
    url = body.split("Unsubscribe: ", 1)[1].splitlines()[0]
    assert url.startswith("https://example.org/api/alerts/unsubscribe?token=")
    payload = alerts.verify_unsubscribe_token(_token_from_url(url))
    assert payload["email"] == "one@example.com"
    assert payload["kind"] == "member_vote"


def test_list_unsubscribe_header_is_set(db):
    _subscribe("one@example.com")

    alerts.queue_alert("member_vote", "Subject", "Body", bioguide_id="A000055")

    header = db[0]["list_unsubscribe"]
    assert header.startswith("https://example.org/api/alerts/unsubscribe?token=")
    assert alerts.verify_unsubscribe_token(_token_from_url(header))["email"] == "one@example.com"


def test_render_unsubscribe_url_roundtrip():
    url = alerts.render_unsubscribe_url("Person@Example.com", "weekly_digest")
    token = _token_from_url(url)
    payload = alerts.verify_unsubscribe_token(token)
    assert payload == {"email": "person@example.com", "kind": "weekly_digest", "bioguideId": ""}


def test_verify_rejects_tampered_token():
    token = alerts.unsubscribe_token("a@example.com", "member_vote")
    encoded, sig = token.split(".")
    assert alerts.verify_unsubscribe_token(f"{encoded}x.{sig}") is None
    assert alerts.verify_unsubscribe_token("garbage") is None
    assert alerts.verify_unsubscribe_token("") is None


def test_alerts_disabled_is_a_noop(monkeypatch, db):
    _subscribe("one@example.com")
    monkeypatch.setattr(alerts.settings, "alerts_enabled", False)

    assert alerts.queue_alert("member_vote", "Subject", "Body") == {
        "sent": 0,
        "failed": 0,
        "skipped": 0,
    }
    assert alerts.dispatch_pending_alerts() == {"sent": 0, "failed": 0, "skipped": 0}
    assert db == []


def test_unconfigured_smtp_is_a_noop(monkeypatch, db):
    _subscribe("one@example.com")
    monkeypatch.setattr(alerts.settings, "smtp_password", "")

    assert alerts.dispatch_pending_alerts() == {"sent": 0, "failed": 0, "skipped": 0}
    assert db == []


def test_dispatch_drains_queue(db):
    _subscribe("one@example.com")
    alerts.enqueue_pending("member_vote", "Queued", "Body")
    assert alerts.pending_count() == 1

    summary = alerts.dispatch_pending_alerts()

    assert summary["sent"] == 1
    assert alerts.pending_count() == 0
    # Second call has nothing left to send.
    assert alerts.dispatch_pending_alerts() == {"sent": 0, "failed": 0, "skipped": 0}


def test_compose_body_appends_unsubscribe():
    body = alerts._body_with_unsubscribe("Hello", "a@example.com", "member_vote", "")
    assert body.startswith("Hello\n\n--\n")
    assert "api/alerts/unsubscribe?token=" in body
