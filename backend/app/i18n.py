"""Minimal backend translations for API-rendered labels and error copy.

The frontend owns its own translation layer; this covers strings the API emits
itself (JSON error details, digest emails, exported CSV headers). Only core UI
labels are translated — anything missing falls back to English so a partial
translation can never produce an empty string or a 500.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = ("en", "es")
DEFAULT_LOCALE = "en"

# Keep keys stable and dotted: they are referenced from routes and email bodies.
_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "nav.bills": "Bills",
        "nav.members": "Members",
        "nav.states": "States",
        "nav.metrics": "Metrics",
        "nav.about": "About",
        "nav.donate": "Donate",
        "vote.not_voting": "Not Voting",
        "vote.yes": "Yes",
        "vote.no": "No",
        "error.generic": "Something went wrong. Please try again.",
        "error.not_found": "Not found",
        "error.rate_limited": "Too many requests. Please try again later.",
    },
    "es": {
        "nav.bills": "Proyectos de ley",
        "nav.members": "Legisladores",
        "nav.states": "Estados",
        "nav.metrics": "Métricas",
        "nav.about": "Acerca de",
        "nav.donate": "Donar",
        "vote.not_voting": "No votó",
        "vote.yes": "Sí",
        "vote.no": "No",
        "error.generic": "Algo salió mal. Inténtalo de nuevo.",
        "error.not_found": "No encontrado",
        "error.rate_limited": "Demasiadas solicitudes. Inténtalo más tarde.",
    },
}


def normalize_locale(locale: str | None) -> str:
    """Map a locale tag (``es-MX``, ``ES``, ``es_419``) to a supported code."""
    raw = (locale or "").strip().lower().replace("_", "-")
    if not raw:
        return DEFAULT_LOCALE
    primary = raw.split("-", 1)[0]
    return primary if primary in SUPPORTED_LOCALES else DEFAULT_LOCALE


def translate(key: str, locale: str = DEFAULT_LOCALE, **kwargs: object) -> str:
    """Translate ``key``, falling back to English and then to the key itself.

    Unknown ``kwargs`` placeholders are left untouched rather than raising, so a
    template bug can never break a response.
    """
    lang = normalize_locale(locale)
    template = _TRANSLATIONS.get(lang, {}).get(key)
    if template is None:
        template = _TRANSLATIONS[DEFAULT_LOCALE].get(key)
    if template is None:
        logger.debug("Missing translation key: %s", key)
        return key
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        logger.warning("Translation placeholders did not match for key=%s locale=%s", key, lang)
        return template


def locale_from_header(accept_language: str | None) -> str:
    """Pick the best supported locale from an ``Accept-Language`` header.

    Honours ``q=`` weights; an unsupported preference falls back to English
    rather than failing the request.
    """
    header = (accept_language or "").strip()
    if not header:
        return DEFAULT_LOCALE

    candidates: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")):
        chunk = part.strip()
        if not chunk:
            continue
        tag, _, params = chunk.partition(";")
        quality = 1.0
        param = params.strip()
        if param.startswith("q="):
            try:
                quality = float(param[2:])
            except ValueError:
                quality = 0.0
        candidates.append((-quality, index, tag.strip()))

    for _neg_quality, _index, tag in sorted(candidates):
        # Skip unsupported entries so a lower-ranked supported locale can win.
        primary = tag.strip().lower().replace("_", "-").split("-", 1)[0]
        if primary in SUPPORTED_LOCALES:
            return primary
    return DEFAULT_LOCALE
