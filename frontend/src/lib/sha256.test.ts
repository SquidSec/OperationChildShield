import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import { leadingZeroBits, sha256Ascii, sha256Bytes } from "./sha256";

function nodeHash(input: string): string {
  return createHash("sha256").update(input, "utf8").digest("hex");
}

function toHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

describe("sha256", () => {
  it("matches Node's crypto for known vectors", () => {
    expect(toHex(sha256Ascii(""))).toBe(nodeHash(""));
    expect(toHex(sha256Ascii("abc"))).toBe(nodeHash("abc"));
    expect(toHex(sha256Ascii("hello world"))).toBe(nodeHash("hello world"));
  });

  it("matches Node across block boundaries", () => {
    // 55/56/63/64/65 exercise the padding edge cases: the one-byte where the
    // length no longer fits in the final block is the classic bug.
    for (const length of [1, 54, 55, 56, 57, 63, 64, 65, 119, 120, 127, 128, 129, 1000]) {
      const input = "a".repeat(length);
      expect(toHex(sha256Ascii(input))).toBe(nodeHash(input));
    }
  });

  it("matches Node for non-ASCII input", () => {
    for (const input of ["café", "日本語", "emoji 🎉 test", "naïve—dash"]) {
      expect(toHex(sha256Bytes(new TextEncoder().encode(input)))).toBe(nodeHash(input));
    }
  });

  it("matches Node for the challenge format the solver uses", () => {
    const challenge = "9f".repeat(24);
    for (const nonce of ["0", "1", "42", "123456"]) {
      const input = `${challenge}:${nonce}`;
      expect(toHex(sha256Ascii(input))).toBe(nodeHash(input));
    }
  });
});

describe("leadingZeroBits", () => {
  it("counts whole zero bytes then partial bits", () => {
    expect(leadingZeroBits(new Uint8Array([0x00, 0x00]))).toBe(16);
    expect(leadingZeroBits(new Uint8Array([0x00, 0x01]))).toBe(15);
    expect(leadingZeroBits(new Uint8Array([0x80]))).toBe(0);
    expect(leadingZeroBits(new Uint8Array([0x40]))).toBe(1);
    expect(leadingZeroBits(new Uint8Array([0x20]))).toBe(2);
  });

  it("agrees with the hash of a real solution", () => {
    // Find a nonce with at least 8 leading zero bits; cheap and deterministic.
    const challenge = "c0ffee";
    for (let nonce = 0; nonce < 10_000; nonce++) {
      const digest = sha256Ascii(`${challenge}:${nonce}`);
      const bits = leadingZeroBits(digest);
      if (bits >= 8) {
        const hex = toHex(digest);
        expect(hex.startsWith("00")).toBe(true);
        expect(bits).toBeGreaterThanOrEqual(8);
        return;
      }
    }
    throw new Error("no nonce found in the search space");
  });
});
