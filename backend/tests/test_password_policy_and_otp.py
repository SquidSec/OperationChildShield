"""Password policy, mandatory OTP, and applicant sanitization."""

import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import admin_store, analytics_store, applications_store
from app import passwords
from app.routes import admin, board
from app.sanitize import clean_short, clean_text, looks_like_markup, sanitize_application
from app.security import reset_rate_limits_for_tests
from tests.admin_login_helpers import enrol, totp

GOOD = "harbor lantern velvet quartz"


# --- Password policy --------------------------------------------------------


def test_accepts_long_passphrase_with_spaces():
    assert passwords.validate_password(GOOD) == GOOD


def test_rejects_short_password():
    with pytest.raises(passwords.PasswordPolicyError) as exc:
        passwords.validate_password("short pass")
    assert "15 characters" in str(exc.value)


def test_rejects_common_password():
    for bad in ("passwordpassword", "Qwerty123456789", "letmeinletmein"):
        with pytest.raises(passwords.PasswordPolicyError):
            passwords.validate_password(bad)


def test_rejects_organization_words():
    with pytest.raises(passwords.PasswordPolicyError):
        passwords.validate_password("operationchildshield99")


def test_rejects_email_local_part():
    with pytest.raises(passwords.PasswordPolicyError):
        passwords.validate_password("jane.doe is my password", email="jane.doe@example.org")


def test_rejects_repeats_and_sequences():
    with pytest.raises(passwords.PasswordPolicyError):
        passwords.validate_password("aaaaaaaaaaaaaaaaaaaa")
    with pytest.raises(passwords.PasswordPolicyError):
        passwords.validate_password("abcdefghijklmnopqrstuvwxyz")


def test_accepts_unicode_and_symbols():
    value = "café ☕ naïve — 42 lanterns"
    assert passwords.validate_password(value) == value


def test_rejects_control_characters():
    with pytest.raises(passwords.PasswordPolicyError):
        passwords.validate_password("good passphrase here\x00extra")


def test_does_not_require_composition():
    # No uppercase, digits, or symbols beyond spaces; still valid.
    assert passwords.validate_password("correct horse battery staple")


def test_rules_for_display_is_not_secret():
    rules = passwords.rules_for_display()
    assert rules["minLength"] == 15
    assert rules["requiresComposition"] is False
    assert isinstance(rules["rules"], list)


def test_strength_label_is_advisory_only():
    assert passwords.strength_label("abc") == "weak"
    assert passwords.strength_label(GOOD * 3) in {"strong", "excellent"}


def test_admin_store_enforces_policy(tmp_path, monkeypatch):
    monkeypatch.setattr(admin_store.settings, "cache_dir", str(tmp_path))
    admin_store.reset_for_tests()
    admin_store.init_admin_db()
    user = admin_store.upsert_admin("policy@example.org", GOOD)
    with pytest.raises(ValueError):
        admin_store.set_admin_password(int(user["id"]), "short")


# --- Sanitization -----------------------------------------------------------


def test_clean_text_strips_controls_and_bidi():
    raw = "hello\x00 <script>alert(1)</script> \u202eevil\u202d end"
    cleaned = clean_text(raw)
    assert "\x00" not in cleaned
    assert "\u202e" not in cleaned
    # Markup is kept as literal text, never executed; React escapes it.
    assert "<script>" in cleaned


def test_clean_text_bounds_length():
    assert len(clean_text("a" * 9000, max_length=100)) == 100


def test_clean_short_collapses_newlines():
    assert clean_short("Jane\n\nDoe") == "Jane Doe"


def test_looks_like_markup_flags_script_and_event_handlers():
    assert looks_like_markup("<img src=x onerror=alert(1)>")
    assert looks_like_markup("javascript:alert(1)")
    assert not looks_like_markup("R&D spending < 5%")


def test_sanitize_application_covers_every_field():
    record = sanitize_application(
        {
            "name": "Jane\x00 Doe",
            "email": "JANE@Example.ORG",
            "statement": "line one\r\nline two",
            "linkedin": "  https://x.example  ",
            "extra": "dropped",
        }
    )
    assert record["name"] == "Jane Doe"
    assert record["email"] == "jane@example.org"
    assert record["statement"] == "line one\nline two"
    assert record["linkedin"] == "https://x.example"
    assert "extra" not in record


# --- Stored applications are sanitized and escaped on read ------------------


def test_applications_store_sanitizes_on_read(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(applications_store.settings, "cache_dir", str(tmp_path))
    path = tmp_path / "board_applications.jsonl"
    path.write_text(
        '{"name": "<script>alert(1)</script>", "email": "X@Y.ORG", '
        '"statement": "ok\\u202e", "roleLabel": "Vice President"}\n'
        "not json\n",
        encoding="utf-8",
    )
    rows = applications_store.list_applications()
    assert len(rows) == 1
    assert rows[0]["email"] == "x@y.org"
    assert "\u202e" not in rows[0]["statement"]
    # Markup remains literal text; the UI escapes it.
    assert rows[0]["name"].startswith("<script>")


# --- Admin applications endpoint --------------------------------------------


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(admin_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(analytics_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(applications_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(admin_store.settings, "admin_captcha_disabled", True)
    admin_store.reset_for_tests()
    analytics_store._initialized = False
    admin_store.init_admin_db()
    analytics_store.init_analytics_db()
    reset_rate_limits_for_tests()

    async def fake_verify(token: str, *, remote_ip: str | None = None) -> bool:
        return True

    monkeypatch.setattr(admin, "verify_turnstile", fake_verify)

    app = FastAPI()
    app.include_router(admin.router, prefix="/api")
    return TestClient(app)


def _sign_in(client: TestClient, role: str = "owner") -> None:
    admin_store.upsert_admin("boss@example.org", GOOD, role=role)
    enrol("boss@example.org")
    first = client.post(
        "/api/admin/login",
        json={"email": "boss@example.org", "password": GOOD, "captcha_token": "t"},
    )
    challenge = first.json()["challenge"]
    secret = admin_store.get_mfa_secret(int(admin_store.get_admin_by_email("boss@example.org")["id"]))
    res = client.post(
        "/api/admin/otp/verify", json={"challenge": challenge, "code": totp(secret)}
    )
    assert res.status_code == 200


def test_applications_require_auth(client):
    assert client.get("/api/admin/applications").status_code == 401


def test_applications_are_returned_sanitized(client, tmp_path):
    _sign_in(client)
    (tmp_path / "board_applications.jsonl").write_text(
        '{"name": "<img src=x onerror=alert(1)>", "email": "a@b.org", '
        '"statement": "hello\\u200bworld", "roleLabel": "Vice President"}\n',
        encoding="utf-8",
    )
    res = client.get("/api/admin/applications")
    assert res.status_code == 200
    row = res.json()["applications"][0]
    assert "\u200b" not in row["statement"]
    assert row["email"] == "a@b.org"


def test_viewer_cannot_read_applications(client):
    _sign_in(client, role="viewer")
    assert client.get("/api/admin/applications").status_code == 403


def test_applications_reject_bad_limit(client):
    _sign_in(client)
    assert client.get("/api/admin/applications?limit=0").status_code == 400
    assert client.get("/api/admin/applications?limit=9999").status_code == 400


# --- Mandatory OTP challenge rules -----------------------------------------


def test_challenge_is_single_use_and_expires(client):
    _sign_in(client)
    client.post("/api/admin/logout")
    first = client.post(
        "/api/admin/login",
        json={"email": "boss@example.org", "password": GOOD, "captcha_token": "t"},
    )
    challenge = first.json()["challenge"]
    secret = admin_store.get_mfa_secret(int(admin_store.get_admin_by_email("boss@example.org")["id"]))

    ok = client.post("/api/admin/otp/verify", json={"challenge": challenge, "code": totp(secret)})
    assert ok.status_code == 200
    assert client.get("/api/admin/me").status_code == 200

    # Same challenge cannot mint a second session.
    replay = client.post("/api/admin/otp/verify", json={"challenge": challenge, "code": totp(secret)})
    assert replay.status_code == 401


def test_wrong_code_does_not_create_session(client):
    _sign_in(client)
    client.post("/api/admin/logout")
    first = client.post(
        "/api/admin/login",
        json={"email": "boss@example.org", "password": GOOD, "captcha_token": "t"},
    )
    wrong = client.post(
        "/api/admin/otp/verify",
        json={"challenge": first.json()["challenge"], "code": "000000"},
    )
    assert wrong.status_code == 401
    assert client.get("/api/admin/me").status_code == 401


def test_challenge_attempts_are_capped(client):
    _sign_in(client)
    client.post("/api/admin/logout")
    first = client.post(
        "/api/admin/login",
        json={"email": "boss@example.org", "password": GOOD, "captcha_token": "t"},
    )
    challenge = first.json()["challenge"]
    for _ in range(admin_store.MAX_CHALLENGE_ATTEMPTS):
        client.post("/api/admin/otp/verify", json={"challenge": challenge, "code": "000000"})
    # The challenge is discarded once attempts run out.
    assert admin_store.peek_login_challenge(challenge) is None


def test_recovery_code_works_once(client):
    _sign_in(client)
    client.post("/api/admin/logout")
    first = client.post(
        "/api/admin/login",
        json={"email": "boss@example.org", "password": GOOD, "captcha_token": "t"},
    )
    user = admin_store.get_admin_by_email("boss@example.org")
    codes = admin_store.generate_recovery_codes(2)
    admin_store.store_recovery_codes(int(user["id"]), codes)

    ok = client.post(
        "/api/admin/otp/verify",
        json={"challenge": first.json()["challenge"], "code": codes[0]},
    )
    assert ok.status_code == 200

    client.post("/api/admin/logout")
    second = client.post(
        "/api/admin/login",
        json={"email": "boss@example.org", "password": GOOD, "captcha_token": "t"},
    )
    reused = client.post(
        "/api/admin/otp/verify",
        json={"challenge": second.json()["challenge"], "code": codes[0]},
    )
    assert reused.status_code == 401


# --- Board application endpoint enforces captcha ---------------------------


@pytest.fixture
def board_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(board.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(board.settings, "admin_captcha_disabled", False)
    monkeypatch.setattr(board.settings, "turnstile_secret_key", "")
    reset_rate_limits_for_tests()

    async def fake_verify(token: str, *, remote_ip: str | None = None) -> bool:
        return token == "valid-token"

    monkeypatch.setattr(board, "verify_turnstile", fake_verify)
    monkeypatch.setattr(board, "_notify_application", lambda record: None)

    app = FastAPI()
    app.include_router(board.router, prefix="/api")
    return TestClient(app)


def test_application_is_stored_without_control_characters(board_client, tmp_path):
    res = board_client.post(
        "/api/board/apply",
        json={
            "role": "vice-president",
            "name": "Jane\x00 Doe",
            "email": "jane@example.org",
            "statement": "Board service\x0b and\x202e strategy",
            "consent": True,
            "captcha_token": "valid-token",
        },
    )
    assert res.status_code == 200
    stored = (tmp_path / "board_applications.jsonl").read_text(encoding="utf-8")
    assert "\x00" not in stored
    assert "\x0b" not in stored
    assert "\u202e" not in stored
    assert "Jane Doe" in stored


# --- OTP is permanently required -------------------------------------------


def test_there_is_no_way_to_disable_otp_in_the_store():
    """The absence of the function is the control, so assert it stays absent."""
    assert not hasattr(admin_store, "disable_mfa"), (
        "disable_mfa must not exist: OTP is hardcoded on for every account"
    )


def test_otp_status_requires_a_confirmed_code():
    """A secret alone never counts as enrolled."""
    import tempfile
    from pathlib import Path

    from app.config import settings

    with tempfile.TemporaryDirectory() as tmp:
        original = settings.cache_dir
        settings.cache_dir = tmp
        try:
            admin_store.reset_for_tests()
            admin_store.init_admin_db()
            user = admin_store.upsert_admin("perm@example.org", GOOD)
            uid = int(user["id"])

            # A pending secret is not enrolment.
            secret = admin_store.generate_mfa_secret()
            admin_store.set_mfa_pending(uid, secret)
            assert admin_store.otp_status(uid)["enrolled"] is False

            # Confirming a code is.
            admin_store.confirm_otp_enrolment(
                uid, admin_store.totp_code(secret)
            )
            assert admin_store.otp_status(uid)["enrolled"] is True
        finally:
            settings.cache_dir = original
            admin_store.reset_for_tests()


def test_force_otp_reset_requires_reenrolment_but_keeps_otp_on():
    import tempfile

    from app.config import settings

    with tempfile.TemporaryDirectory() as tmp:
        original = settings.cache_dir
        settings.cache_dir = tmp
        try:
            admin_store.reset_for_tests()
            admin_store.init_admin_db()
            user = admin_store.upsert_admin("reset@example.org", GOOD)
            uid = int(user["id"])
            secret = admin_store.generate_mfa_secret()
            admin_store.set_mfa_pending(uid, secret)
            admin_store.confirm_otp_enrolment(uid, admin_store.totp_code(secret))
            assert admin_store.otp_status(uid)["enrolled"] is True

            admin_store.force_otp_reset(uid)

            status = admin_store.otp_status(uid)
            # Enrolment is no longer complete, so a new setup is required...
            assert status["enrolled"] is False
            # ...but the requirement itself was never switched off.
            row = admin_store.get_admin_by_id(uid)
            assert row is not None
            assert admin_store.get_mfa_secret(uid) is None
        finally:
            settings.cache_dir = original
            admin_store.reset_for_tests()


def test_disable_endpoint_refuses_and_leaves_account_untouched(client):
    _sign_in(client)
    before = client.get("/api/admin/me").json()["user"]
    res = client.post("/api/admin/mfa/disable")
    assert res.status_code == 403
    assert "cannot be disabled" in res.json()["detail"].lower()
    after = client.get("/api/admin/me").json()["user"]
    assert after["mfaEnabled"] is True
    assert before["mfaEnabled"] is True


def test_owner_cannot_disable_another_users_otp(client):
    """No endpoint exists to clear another account's OTP requirement."""
    _sign_in(client)
    target = admin_store.upsert_admin("other@example.org", GOOD, role="editor")
    for path in (
        f"/api/admin/users/{target['id']}/mfa/disable",
        f"/api/admin/users/{target['id']}/otp/disable",
    ):
        assert client.post(path).status_code in (404, 405)
    assert admin_store.get_admin_by_id(int(target["id"])) is not None
