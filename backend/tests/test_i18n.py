import pytest

from app import i18n


def test_supported_locales_are_exposed():
    assert i18n.SUPPORTED_LOCALES == ("en", "es")


def test_translate_returns_key_for_missing_entries():
    assert i18n.translate("does.not.exist") == "does.not.exist"


def test_translate_defaults_to_english():
    assert i18n.translate("vote.yes") == "Yes"


def test_translate_spanish():
    assert i18n.translate("vote.not_voting", locale="es") == "No votó"


def test_translate_unknown_locale_falls_back_to_english():
    assert i18n.translate("nav.bills", locale="de") == "Bills"


def test_translate_region_tag_normalizes():
    assert i18n.translate("nav.metrics", locale="es-MX") == "Métricas"


def test_translate_interpolates_kwargs():
    i18n._TRANSLATIONS["en"]["greeting"] = "Hello, {name}"
    try:
        assert i18n.translate("greeting", name="Ada") == "Hello, Ada"
    finally:
        del i18n._TRANSLATIONS["en"]["greeting"]


def test_translate_bad_placeholder_does_not_raise():
    i18n._TRANSLATIONS["en"]["bad"] = "Hi {missing}"
    try:
        assert i18n.translate("bad", other="x") == "Hi {missing}"
    finally:
        del i18n._TRANSLATIONS["en"]["bad"]


def test_locale_from_header_empty():
    assert i18n.locale_from_header("") == "en"
    assert i18n.locale_from_header(None) == "en"


def test_locale_from_header_picks_supported():
    assert i18n.locale_from_header("es-MX,es;q=0.9,en;q=0.8") == "es"
    assert i18n.locale_from_header("en-US,en;q=0.9") == "en"


def test_locale_from_header_respects_quality():
    assert i18n.locale_from_header("fr;q=1.0,es;q=0.7") == "es"
    assert i18n.locale_from_header("es;q=0.2,en;q=0.9") == "en"


def test_locale_from_header_unsupported_only():
    assert i18n.locale_from_header("de-DE,fr-CA") == "en"


def test_locale_from_header_wildcard():
    assert i18n.locale_from_header("*") == "en"


def test_locale_from_header_malformed_quality():
    assert i18n.locale_from_header("es;q=abc,en") == "en"


@pytest.mark.parametrize("raw", ["ES", "es_419", "es-CL"])
def test_normalize_locale_variants(raw):
    assert i18n.normalize_locale(raw) == "es"
