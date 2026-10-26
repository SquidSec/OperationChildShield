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