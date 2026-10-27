"""Bot classification for traffic analytics.

Ported from the SquidHackerBlog `squidsec-traffic` plugin, which tags every hit
with a reason code so filtered traffic can be audited rather than silently
dropped. Order matters: the first match wins, cheapest first, so most bots are
caught without any lookups.

Design notes carried over from the original:
- A reason code is always recorded, so a false positive is diagnosable.
- Browser-header plausibility is only judged when real headers exist; an
  offline reclassifier has none and would otherwise flag every stored row.
- Datacenter and rate signals are opt-in because they need extra data.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

# Reason code -> human label, surfaced in the admin UI.
REASONS: dict[str, str] = {
    "no-ua": "No user agent",
    "declared-search": "Search engine bot",
    "declared-social": "Social / link preview",
    "declared-ai": "AI crawler",
    "declared-feed": "Feed reader",
    "declared-other": "Other declared bot",
    "client-lib": "HTTP client library",
    "scanner": "Security scanner",
    "monitor": "Uptime / speed monitor",
    "prefetch": "Browser prefetch",
    "malformed-ua": "Malformed user agent",
    "non-browser": "Non-browser user agent",
    "implausible-headers": "Browser UA without browser headers",
    "rate-limit": "Request rate exceeded",
    "datacenter": "Datacenter / hosting network",
    "internal": "Admin / staff navigation",
}

SEARCH = re.compile(
    r"googlebot|google-inspectiontool|googleother|mediapartners-google|adsbot-google"
    r"|bingbot|bingpreview|slurp|duckduckbot|baiduspider|yandex(bot|images)|sogou"
    r"|exabot|applebot|petalbot|seznam|qwantify|mojeek|coccoc|ahrefsbot|semrushbot"
    r"|mj12bot|dotbot|rogerbot|screaming frog",
    re.I,
)
SOCIAL = re.compile(
    r"facebookexternalhit|facebookcatalog|twitterbot|linkedinbot|slackbot|discordbot"
    r"|telegrambot|whatsapp|pinterestbot|embedly|redditbot|quora link preview"
    r"|vkshare|w3c_validator|skypeuripreview|iframely|mastodon|bluesky|threads",
    re.I,
)
AI = re.compile(
    r"gptbot|chatgpt-user|oai-searchbot|claude-web|claude-user|anthropic|bytespider"
    r"|ccbot|perplexitybot|perplexity-user|amazonbot|google-extended"
    r"|meta-externalagent|cohere-ai|youbot|timpibot|omgili|diffbot|img2dataset",
    re.I,
)
FEED = re.compile(
    r"feedly|inoreader|feedbin|newsblur|feedfetcher|rssowl|the old reader"
    r"|theoldreader|netnewswire|freshreader|tiny tiny rss|akregator|feedspot|upflow",
    re.I,
)
OTHER_BOT = re.compile(
    r"bot\b|crawl|spider|slurp|archiver|ia_archiver|archive\.org_bot|harvest|scrapy"
    r"|sistrix|screaming|linkchecker|validator|headlesschrome|phantomjs|puppeteer"
    r"|playwright|selenium|sitebulb|serpstat|majestic|deepcrawl|botify|oncrawl"
    r"|contentking|lumar|sitemap|pingdom|gtmetrix|lighthouse|webpagetest"
    r"|uptimerobot|statuscake|site24x7|newrelic|datadog|check_http|nagios|zabbix"
    r"|kuma|freshping|hetrixtools",
    re.I,
)
CLIENT = re.compile(
    r"curl|wget|go-http-client|java/|okhttp|axios|node-fetch|node\.js|guzzle"
    r"|libwww-perl|python-requests|python/|python-urllib|aiohttp|httpx|httpie"
    r"|requests/|scrapy|php/|ruby|perl|powershell|postmanruntime|insomnia"
    r"|httpclient|restsharp|apache-httpclient|mechanize|winhttp|libcurl"
    r"|websiphon|terracotta|colly|reqwest|faraday|nokogiri|http\.rb",
    re.I,
)
SCANNER = re.compile(
    r"panscient|crusader[- ]?worker|l9explore|palo alto|security research|softsec"
    r"|vulndiscovery|visionheight|cms-security|netsystemsresearch"
    r"|internet-measurement|binaryedge|shodan|censys|zmap|masscan|nmap|nikto|nuclei"
    r"|acunetix|nessus|openvas|qualys|wpscan|dirbuster|gobuster|feroxbuster|ffuf"
    r"|sqlmap|xpan|zgrab|project25499|expanse|shadowserver|driftnet|stretchoid"
    r"|cyberia|alphastrike|ipip\.net|netcraft|rapid7|recordedfuture|recon-ng"
    r"|sn1per|detectify|intruder",
    re.I,
)
MONITOR = re.compile(
    r"pingdom|gtmetrix|lighthouse|webpagetest|uptimerobot|statuscake|site24x7"
    r"|newrelic|datadog|betteruptime|freshping|hetrixtools|checkly|sematext"
    r"|montastic|updown\.io",
    re.I,
)
PREFETCH = re.compile(
    r"prefetch proxy|chrome privacy preserving prefetch|prerender|instantpage"
    r"|speculation-rules",
    re.I,
)
# Cloud / hosting org names, as returned by an IP intelligence lookup.
HOSTING_ORG = re.compile(
    r"\b(amazon|aws|microsoft|azure|google llc|google cloud|digitalocean|linode"
    r"|akamai|hetzner|ovh|scaleway|vultr|choopa|contabo|leaseweb|alibaba|aliyun"
    r"|tencent|oracle cloud|cloudflare|fastly|m247|psychz|colocrossing|quadranet"
    r"|hostinger|godaddy|namecheap|ionos|rackspace|equinix|softlayer|upcloud"
    r"|kamatera|packet|servers\.com|hostwinds|interserver|nfoservers|gigenet"
    r"|privex|buyvm|frantech)\b",
    re.I,
)

# A real browser UA starts with one of these product tokens.
_BROWSER_PREFIX = re.compile(
    r"^(Mozilla|Opera|Edg|Chrome|Safari|Firefox|Version|Dalvik)", re.I
)

_ASSET_PATH = re.compile(
    r"\.(css|js|map|jpg|jpeg|png|gif|webp|svg|woff2?|ico|xml|txt)(\?|$)", re.I
)
_ENDPOINT_PATH = re.compile(r"^(/api|/wp-json|/xmlrpc\.php)(/|$)", re.I)
_PROBE_PATH = re.compile(
    r"/(wp-login|wp-admin|admin-ajax|\.env|\.git|phpmyadmin|xmlrpc\.php"
    r"|vendor/phpunit|actuator|\.aws|config\.json)",
    re.I,
)


@dataclass(frozen=True)
class Verdict:
    is_bot: bool
    reason: str = ""

    @property
    def label(self) -> str:
        if not self.reason:
            return "Not filtered"
        return REASONS.get(self.reason, self.reason)


def _bot(reason: str) -> Verdict:
    return Verdict(True, reason)


HUMAN = Verdict(False, "")


def classify(
    user_agent: str | None,
    *,
    headers: dict[str, str] | None = None,
    rate_exceeded: bool = False,
    datacenter_org: str = "",
) -> Verdict:
    """Classify one request.

    ``headers`` should be the real request headers when available. When it is
    None (an offline reclassification of stored rows), the browser-header
    plausibility check is skipped, since stored rows carry no headers and every
    row would otherwise be flagged.
    """
    ua = (user_agent or "").strip()

    if not ua:
        return _bot("no-ua")

    lowered = {k.lower(): v for k, v in (headers or {}).items()}
    purpose = " ".join(
        lowered.get(k, "")
        for k in ("sec-purpose", "purpose", "x-moz", "x-purpose")
    )
    if purpose and re.search(r"prefetch|prerender|preview", purpose, re.I):
        return _bot("prefetch")

    if SCANNER.search(ua):
        return _bot("scanner")
    if MONITOR.search(ua):
        return _bot("monitor")
    if PREFETCH.search(ua):
        return _bot("prefetch")

    if SEARCH.search(ua):
        return _bot("declared-search")
    if AI.search(ua):
        return _bot("declared-ai")
    if SOCIAL.search(ua):
        return _bot("declared-social")
    if FEED.search(ua):
        return _bot("declared-feed")
    if OTHER_BOT.search(ua):
        return _bot("declared-other")

    if CLIENT.search(ua):
        return _bot("client-lib")

    # Embedded quotes or JSON escapes mean a scraped or replayed header.
    if '"' in ua or '\\"' in ua or "\\u" in ua:
        return _bot("malformed-ua")

    if not _BROWSER_PREFIX.match(ua):
        return _bot("non-browser")

    if headers is not None:
        accept = lowered.get("accept", "")
        lang = lowered.get("accept-language", "")
        if not accept and not lang:
            return _bot("implausible-headers")

    if rate_exceeded:
        return _bot("rate-limit")

    if datacenter_org and HOSTING_ORG.search(datacenter_org):
        return _bot("datacenter")

    return HUMAN


def is_asset_path(path: str) -> bool:
    return bool(_ASSET_PATH.search(path or ""))


def is_endpoint_path(path: str) -> bool:
    """Routes that never render a page for a reader."""
    value = (path or "").lower()
    if not value:
        return False
    if _ENDPOINT_PATH.match(value):
        return True
    return value in ("/admin-ajax", "/wp-cron", "/wp-login", "/wp-login.php")


def is_probe_path(path: str) -> bool:
    return bool(_PROBE_PATH.search(path or ""))


class RateTracker:
    """Sliding-minute counter per (ip, ua) used for the rate signal.

    In-process only, matching the rest of the rate limiting. A single instance
    is the deployment shape today; a shared store would be the next step.
    """

    def __init__(self, limit: int = 60, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._last_sweep = 0.0

    def exceeded(self, ip: str, user_agent: str) -> bool:
        if self.limit <= 0:
            return False
        key = f"{ip}|{(user_agent or '')[:80]}"
        now = time.monotonic()
        bucket = self._hits.setdefault(key, [])
        cutoff = now - self.window
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        bucket.append(now)
        if now - self._last_sweep > 300:
            self._last_sweep = now
            for stale in [k for k, v in self._hits.items() if not v or v[-1] < cutoff]:
                self._hits.pop(stale, None)
        return len(bucket) > self.limit

    def reset(self) -> None:
        self._hits.clear()
