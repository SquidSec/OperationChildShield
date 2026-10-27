"""QR code encoder for the authenticator setup link.

Hand-rolled so admin login needs no extra dependency and no network call. The
algorithm follows the standard (ISO/IEC 18004) construction: byte mode, error
correction level M, versions 1-10, single block-group interleaving with the
required padding placeholder.

Correctness is pinned by tests that compare the produced matrix cell-for-cell
against the reference `qrcode` library for several payloads. That is stronger
than checking shape: any mistake in masking, format bits, or interleaving
changes the matrix.
"""

from __future__ import annotations

# Error correction level M tables, indexed by version (1-10 only).
_ECC_PER_BLOCK = {1: 10, 2: 16, 3: 26, 4: 18, 5: 24, 6: 16, 7: 18, 8: 22, 9: 22, 10: 26}
_NUM_BLOCKS = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 4, 7: 4, 8: 4, 9: 5, 10: 5}

# Standard alignment-pattern centres.
_ALIGNMENT = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
    7: [6, 22, 38],
    8: [6, 24, 42],
    9: [6, 26, 46],
    10: [6, 28, 50],
}


def _num_raw_data_modules(version: int) -> int:
    """Count data modules before ECC (excludes function patterns)."""
    result = (16 * version + 128) * version + 64
    if version >= 2:
        num_align = version // 7 + 2
        result -= (25 * num_align - 10) * num_align - 55
        if version >= 7:
            result -= 36
    return result


def _gf_mul(x: int, y: int) -> int:
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z & 0xFF


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


def _choose_version(byte_length: int) -> int:
    for version in range(1, 11):
        capacity = _num_raw_data_modules(version) // 8
        ecc_total = _ECC_PER_BLOCK[version] * _NUM_BLOCKS[version]
        header_bits = 4 + (8 if version <= 9 else 16)
        if header_bits + byte_length * 8 <= (capacity - ecc_total) * 8:
            return version
    raise ValueError("Data too long for a supported QR version")


def _encode_codewords(payload: bytes, version: int) -> list[int]:
    capacity = _num_raw_data_modules(version) // 8
    ecc_total = _ECC_PER_BLOCK[version] * _NUM_BLOCKS[version]
    data_capacity = capacity - ecc_total

    bits: list[int] = []

    def push(value: int, length: int) -> None:
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)

    push(0b0100, 4)
    push(len(payload), 8 if version <= 9 else 16)
    for byte in payload:
        push(byte, 8)

    push(0, min(4, data_capacity * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)

    codewords = [
        int("".join(str(b) for b in bits[i : i + 8]), 2) for i in range(0, len(bits), 8)
    ]
    pad = 0xEC
    while len(codewords) < data_capacity:
        codewords.append(pad)
        pad = 0x11 if pad == 0xEC else 0xEC
    return codewords


def _add_ecc_interleaved(data: list[int], version: int) -> list[int]:
    num_blocks = _NUM_BLOCKS[version]
    ecc_len = _ECC_PER_BLOCK[version]
    raw_codewords = _num_raw_data_modules(version) // 8
    num_short_blocks = num_blocks - raw_codewords % num_blocks
    short_data_len = raw_codewords // num_blocks - ecc_len
    divisor = _rs_divisor(ecc_len)

    blocks: list[list[int | None]] = []
    k = 0
    for i in range(num_blocks):
        length = short_data_len + (0 if i < num_short_blocks else 1)
        chunk = data[k : k + length]
        k += length
        ecc = _rs_remainder(chunk, divisor)
        # Short blocks carry a padding placeholder so every block has the same
        # length; it is skipped during interleaving, as the spec requires.
        blocks.append(chunk + ([None] if i < num_short_blocks else []) + ecc)

    result: list[int] = []
    for i in range(len(blocks[0])):
        for block in blocks:
            value = block[i]
            if value is not None:
                result.append(value)
    return result


class _Builder:
    def __init__(self, version: int) -> None:
        self.version = version
        self.size = version * 4 + 17
        self.modules = [[False] * self.size for _ in range(self.size)]
        self.is_function = [[False] * self.size for _ in range(self.size)]

    def set_function(self, x: int, y: int, dark: bool) -> None:
        self.modules[y][x] = dark
        self.is_function[y][x] = True

    def draw_function_patterns(self) -> None:
        size = self.size
        for i in range(size):
            self.set_function(6, i, i % 2 == 0)
            self.set_function(i, 6, i % 2 == 0)

        for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < size and 0 <= y < size:
                        dist = max(abs(dx), abs(dy))
                        self.set_function(x, y, dist not in (2, 4))

        positions = _ALIGNMENT[self.version]
        for cy in positions:
            for cx in positions:
                # Skip centres that collide with the finder patterns.
                if (cx == 6 and cy == 6) or (cx == 6 and cy == size - 7) or (
                    cx == size - 7 and cy == 6
                ):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set_function(
                            cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1
                        )

        self.draw_format_bits(0)
        self.draw_version()

    def draw_format_bits(self, mask: int) -> None:
        data = (0b00 << 3) | mask  # ECC level M is 0b00
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = ((data << 10) | rem) ^ 0x5412

        def bit(i: int) -> bool:
            return ((bits >> i) & 1) != 0

        for i in range(6):
            self.set_function(8, i, bit(i))
        self.set_function(8, 7, bit(6))
        self.set_function(8, 8, bit(7))
        self.set_function(7, 8, bit(8))
        for i in range(9, 15):
            self.set_function(14 - i, 8, bit(i))

        size = self.size
        for i in range(8):
            self.set_function(size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self.set_function(8, size - 15 + i, bit(i))
        self.set_function(8, size - 8, True)  # dark module

    def draw_version(self) -> None:
        if self.version < 7:
            return
        rem = self.version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = (self.version << 12) | rem
        size = self.size
        for i in range(18):
            dark = ((bits >> i) & 1) != 0
            a = size - 11 + i % 3
            b = i // 3
            self.set_function(a, b, dark)
            self.set_function(b, a, dark)

    def draw_codewords(self, codewords: list[int]) -> None:
        size = self.size
        bit_index = 0
        total_bits = len(codewords) * 8
        col = size - 1
        upward = True

        while col > 0:
            if col == 6:
                col -= 1
            for vert in range(size):
                y = size - 1 - vert if upward else vert
                for x in (col, col - 1):
                    if not self.is_function[y][x]:
                        if bit_index < total_bits:
                            byte = codewords[bit_index >> 3]
                            dark = ((byte >> (7 - (bit_index & 7))) & 1) != 0
                            self.modules[y][x] = dark
                        bit_index += 1
            upward = not upward
            col -= 2

    def apply_mask(self, mask: int) -> None:
        for y in range(self.size):
            for x in range(self.size):
                if self.is_function[y][x]:
                    continue
                if _mask_bit(mask, x, y):
                    self.modules[y][x] = not self.modules[y][x]

    def penalty(self) -> int:
        size = self.size
        m = self.modules
        score = 0
        for y in range(size):
            run = 1
            for x in range(1, size):
                if m[y][x] == m[y][x - 1]:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + run - 5
                    run = 1
            if run >= 5:
                score += 3 + run - 5
        for x in range(size):
            run = 1
            for y in range(1, size):
                if m[y][x] == m[y - 1][x]:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + run - 5
                    run = 1
            if run >= 5:
                score += 3 + run - 5
        for y in range(size - 1):
            for x in range(size - 1):
                c = m[y][x]
                if c == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    score += 3
        dark = sum(1 for row in m for cell in row if cell)
        total = size * size
        score += (abs(dark * 20 - total * 10) // total) * 10
        return score


def _mask_bit(mask: int, x: int, y: int) -> bool:
    if mask == 0:
        return (x + y) % 2 == 0
    if mask == 1:
        return y % 2 == 0
    if mask == 2:
        return x % 3 == 0
    if mask == 3:
        return (x + y) % 3 == 0
    if mask == 4:
        return (y // 2 + x // 3) % 2 == 0
    if mask == 5:
        return (x * y) % 2 + (x * y) % 3 == 0
    if mask == 6:
        return ((x * y) % 2 + (x * y) % 3) % 2 == 0
    return ((x + y) % 2 + (x * y) % 3) % 2 == 0


def qr_matrix(data: str) -> list[list[bool]]:
    """Return the QR matrix for ``data`` (True = dark module)."""
    payload = data.encode("utf-8")
    version = _choose_version(len(payload))
    codewords = _add_ecc_interleaved(_encode_codewords(payload, version), version)

    best: tuple[int, list[list[bool]]] | None = None
    for mask in range(8):
        builder = _Builder(version)
        builder.draw_function_patterns()
        builder.draw_codewords(codewords)
        builder.apply_mask(mask)
        # Format bits depend on the mask, so redraw them after masking.
        builder.draw_format_bits(mask)
        score = builder.penalty()
        if best is None or score < best[0]:
            best = (score, [row[:] for row in builder.modules])
    assert best is not None
    return best[1]


def qr_svg(data: str, *, module_size: int = 4, border: int = 4) -> str:
    """Inline SVG for ``data``.

    Built entirely from the computed matrix, so the markup contains no
    untrusted text: no script tags, no foreignObject, no external references.
    """
    matrix = qr_matrix(data)
    size = len(matrix)
    dimension = (size + border * 2) * module_size
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{dimension}" '
        f'height="{dimension}" viewBox="0 0 {dimension} {dimension}" '
        'role="img" aria-label="Authenticator setup QR code" '
        'shape-rendering="crispEdges">',
        f'<rect width="{dimension}" height="{dimension}" fill="#ffffff"/>',
        '<path fill="#000000" d="',
    ]
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                px = (x + border) * module_size
                py = (y + border) * module_size
                parts.append(f"M{px} {py}h{module_size}v{module_size}h-{module_size}z")
    parts.append('"/></svg>')
    return "".join(parts)
