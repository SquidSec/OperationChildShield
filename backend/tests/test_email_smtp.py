from app.email_smtp import (
    auto_reply_involve_signup,
    notify_involve_signup,
    sanitize_email_body,
    sanitize_email_header,
)


def test_sanitize_email_header_strips_crlf_and_controls():
    raw = "Alice\r\nBcc: evil@example.com\nX-Inject: 1"
    cleaned = sanitize_email_header(raw)
    assert "\r" not in cleaned
    assert "\n" not in cleaned
    assert "Bcc:" in cleaned  # text may remain, but not as a new header line
    assert cleaned == "Alice Bcc: evil@example.com X-Inject: 1"


def test_sanitize_email_header_truncates():
    assert len(sanitize_email_header("a" * 500, max_length=50)) == 50


def test_sanitize_email_body_normalizes_newlines():
    body = "hello\r\nworld\x00\x07"
    cleaned = sanitize_email_body(body)
    assert cleaned == "hello\nworld"
    assert "\r" not in cleaned
    assert "\x00" not in cleaned


def _enable_smtp(monkeypatch) -> None:
    monkeypatch.setattr("app.email_smtp.settings.smtp_host", "smtp.example.com")
    monkeypatch.setattr("app.email_smtp.settings.smtp_user", "user@example.com")
    monkeypatch.setattr("app.email_smtp.settings.smtp_password", "secret")
    monkeypatch.setattr("app.email_smtp.settings.involve_notify_to", "ops@example.com")
    monkeypatch.setattr("app.email_smtp.settings.involve_send_auto_reply", True)


def test_notify_uses_sanitized_subject(monkeypatch):
    captured: dict = {}

    def fake_send(**kwargs):
        captured.update(kwargs)

    _enable_smtp(monkeypatch)
    monkeypatch.setattr("app.email_smtp.send_email", fake_send)

    ok = notify_involve_signup(
        {
            "name": "Bob\r\nBcc: x@evil.com",
            "email": "bob@example.com",
            "interest": "volunteer\nSubject: pwned",
            "message": "line1\r\nline2",
            "state": "TX",
            "submittedAt": "2026-01-01T00:00:00Z",
        }
    )
    assert ok is True
    assert "\r" not in captured["subject"]
    assert "\n" not in captured["subject"]
    assert "\r" not in captured["body"]
    assert captured["reply_to"] == "bob@example.com"


def test_auto_reply_returns_false_on_send_failure(monkeypatch):
    _enable_smtp(monkeypatch)

    def boom(**_kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr("app.email_smtp.send_email", boom)
    assert auto_reply_involve_signup({"email": "a@b.com", "name": "A"}) is False


def test_auto_reply_is_throttled_per_address(monkeypatch):
    """Repeated signups for one address must not keep generating mail."""
    sent: list[dict] = []
    _enable_smtp(monkeypatch)
    monkeypatch.setattr("app.email_smtp.send_email", lambda **kw: sent.append(kw))
    from app.email_smtp import reset_auto_reply_throttle_for_tests

    reset_auto_reply_throttle_for_tests()

    record = {"email": "victim@example.com", "name": "A"}
    assert auto_reply_involve_signup(record) is True
    assert auto_reply_involve_signup(record) is False
    assert auto_reply_involve_signup(record) is False
    assert len(sent) == 1


def test_auto_reply_is_capped_globally(monkeypatch):
    """A rotating-address attack hits the global hourly cap."""
    _enable_smtp(monkeypatch)
    import app.email_smtp as email_smtp

    monkeypatch.setattr(email_smtp.settings, "auto_reply_max_per_hour", 3)
    monkeypatch.setattr(email_smtp, "send_email", lambda **kw: None)
    from app.email_smtp import reset_auto_reply_throttle_for_tests

    reset_auto_reply_throttle_for_tests()

    results = [
        auto_reply_involve_signup({"email": f"user{i}@example.com", "name": "A"})
        for i in range(6)
    ]
    assert results == [True, True, True, False, False, False]
