import ipaddress

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    congress_api_key: str = ""
    congress_number: int = 119
    cache_ttl_seconds: int = 86400  # 24 hours
    # Comma-separated exact origins (no wildcards). Prod: public HTTPS only.
    cors_origins: str = "http://localhost:3000"
    congress_base_url: str = "https://api.congress.gov/v3"
    cache_dir: str = "/app/data"

    # Proton / SMTP for Join Us form notifications
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    involve_notify_to: str = ""
    # Auto-replies are throttled per recipient and globally (see email_smtp) so an
    # unauthenticated signup cannot use the server to mailbomb arbitrary addresses.
    involve_send_auto_reply: bool = True
    # Max auto-replies to one address per window, and the global hourly cap.
    auto_reply_per_address_hours: float = 24.0
    auto_reply_max_per_hour: int = 60

    # Reverse proxy whose forwarded-IP headers we trust. Loopback + private
    # ranges by default; set to the Caddy address in production.
    trusted_proxy_cidrs: str = "127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

    # Age of raw analytics rows (page views / actions) before pruning.
    analytics_retention_days: int = 90

    # Skip the Congress.gov title check at startup (local UI work; see AGENTS.md).
    skip_bill_verification: bool = False

    # --- Rate limiting / caching backend -------------------------------------
    # Optional Redis URL for shared rate limits across processes. When empty the
    # in-process limiter is used (single-instance default).
    redis_url: str = ""

    # --- Background jobs ------------------------------------------------------
    # Interval in seconds for the in-process scheduler (cache refresh, pruning,
    # digest emails). 0 disables the scheduler thread.
    scheduler_interval_seconds: int = 300
    scheduler_enabled: bool = True

    # --- Email alerts ---------------------------------------------------------
    # Base URL used in outgoing alert emails and unsubscribe links.
    public_site_url: str = "https://operationchildshield.org"
    alerts_enabled: bool = True
    alert_max_attempts: int = 3
    # Local development only: log verification/reset links and return them in
    # the API response instead of relying on a mail server. Never enable in
    # production: the link is account access.
    dev_email_outbox: bool = False
    # Local development only: relax signup/login throttles so repeated manual
    # testing does not lock you out. Ignored unless explicitly set.
    dev_relax_rate_limits: bool = False

    # --- Public API -----------------------------------------------------------
    # Comma-separated API keys for the read-only public API. Empty keeps it off.
    public_api_keys: str = ""
    public_api_rate_limit_per_hour: int = 1000

    # --- Admin hardening ------------------------------------------------------
    admin_require_mfa: bool = False
    admin_lockout_threshold: int = 5
    admin_lockout_minutes: int = 15

    # --- Observability --------------------------------------------------------
    otel_enabled: bool = False
    otel_endpoint: str = ""
    log_json: bool = False
    csp_report_uri: str = ""

    # --- Backups --------------------------------------------------------------
    backup_dir: str = ""
    backup_keep: int = 7

    @property
    def public_api_key_list(self) -> list[str]:
        return [k.strip() for k in self.public_api_keys.split(",") if k.strip()]

    # Admin section. Accounts are seeded via scripts/seed_admin.py; no registration.
    admin_session_hours: int = 12
    # Force the Secure flag; also applied automatically for HTTPS requests.
    admin_cookie_secure: bool = False
    # Cloudflare Turnstile. Verification fails closed when the secret is unset
    # unless ADMIN_CAPTCHA_DISABLED is explicitly true (local dev only).
    turnstile_secret_key: str = ""
    turnstile_site_key: str = ""
    admin_captcha_disabled: bool = False
    # Public origin the browser uses; Turnstile checks the widget hostname.
    admin_allowed_hostnames: str = "operationchildshield.org,www.operationchildshield.org"

    @property
    def captcha_enforced(self) -> bool:
        return bool(self.turnstile_secret_key) and not self.admin_captcha_disabled

    @property
    def admin_allowed_hostname_list(self) -> list[str]:
        return [h.strip().lower() for h in self.admin_allowed_hostnames.split(",") if h.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    @property
    def trusted_proxy_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for raw in self.trusted_proxy_cidrs.split(","):
            cidr = raw.strip()
            if not cidr:
                continue
            try:
                networks.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                continue
        return networks


settings = Settings()
