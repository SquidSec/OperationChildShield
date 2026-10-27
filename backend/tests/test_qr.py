"""QR encoder correctness for the authenticator setup link."""

import pytest

from app import qr

URI = (
    "otpauth://totp/Operation%20Child%20Shield:admin%40example.org"
    "?secret=JBSWY3DPEHPK3PXP&issuer=Operation%20Child%20Shield"
    "&algorithm=SHA1&digits=6&period=30"
)


def _finder_ok(matrix, x0: int, y0: int) -> bool:
    """A finder pattern is a 7x7 ring: dark border, light ring, 3x3 dark core."""
    for dy in range(7):
        for dx in range(7):
            dist = max(abs(dx - 3), abs(dy - 3))
            expected = dist != 2
            if matrix[y0 + dy][x0 + dx] != expected:
                return False
    return True


def test_matrix_is_square_with_expected_version_size():
    matrix = qr.qr_matrix(URI)
    assert len(matrix) == len(matrix[0])
    # Size is 4 * version + 17 for a QR symbol.
    assert (len(matrix) - 17) % 4 == 0
    assert 21 <= len(matrix) <= 57


def test_finder_patterns_and_timing():
    matrix = qr.qr_matrix(URI)
    size = len(matrix)
    assert _finder_ok(matrix, 0, 0)
    assert _finder_ok(matrix, size - 7, 0)
    assert _finder_ok(matrix, 0, size - 7)
    # Timing patterns alternate starting dark at index 6.
    for i in range(8, size - 8):
        assert matrix[6][i] == (i % 2 == 0)
        assert matrix[i][6] == (i % 2 == 0)


def test_dark_module_is_set():
    matrix = qr.qr_matrix(URI)
    size = len(matrix)
    assert matrix[size - 8][8] is True


def test_longer_payload_uses_a_larger_version():
    small = qr.qr_matrix("HELLO")
    large = qr.qr_matrix("x" * 200)
    assert len(large) > len(small)


def test_payload_too_long_is_rejected():
    with pytest.raises(ValueError):
        qr.qr_matrix("x" * 5000)


def test_svg_contains_no_script_or_external_references():
    svg = qr.qr_svg(URI)
    assert svg.startswith("<svg")
    assert "script" not in svg.lower()
    assert "foreignObject" not in svg
    assert "href" not in svg
    assert svg.count("<path") == 1
    assert svg.endswith("</svg>")


def test_svg_geometry_only_from_matrix():
    # The URI must never be embedded as text in the SVG.
    svg = qr.qr_svg(URI)
    assert "otpauth" not in svg
    assert "secret" not in svg


@pytest.mark.parametrize(
    "payload",
    [
        "HELLO",
        URI,
        "x" * 120,
    ],
)
def test_matches_reference_implementation(payload):
    """Cell-for-cell comparison against the `qrcode` library when installed.

    The encoder is hand-rolled, so structural checks alone are not enough; a
    mask or interleaving mistake still yields a plausible-looking grid.
    """
    qrcode = pytest.importorskip("qrcode")
    from qrcode.constants import ERROR_CORRECT_M

    ref = qrcode.QRCode(error_correction=ERROR_CORRECT_M, border=0)
    ref.add_data(payload)
    ref.make(fit=True)
    reference = ref.get_matrix()
    mine = qr.qr_matrix(payload)

    assert len(reference) == len(mine), "version mismatch"
    diffs = sum(
        1
        for y in range(len(mine))
        for x in range(len(mine))
        if bool(reference[y][x]) != mine[y][x]
    )
    assert diffs == 0, f"{diffs} differing modules"
