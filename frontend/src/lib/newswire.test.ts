import { describe, expect, it } from "vitest";
import { parseArticleBody } from "@/components/news/ArticleBody";
import { ROLES, getRole, roleDefaultId } from "@/lib/take-action";

describe("parseArticleBody", () => {
  it("splits headings, paragraphs, and lists", () => {
    const blocks = parseArticleBody(
      "Intro paragraph.\n\n## What happened\n\nSecond paragraph.\n\n- one\n- two\n\n1. first\n2. second"
    );
    expect(blocks.map((b) => b.type)).toEqual(["p", "h2", "p", "ul", "ol"]);
    expect(blocks[1].text).toBe("What happened");
    expect(blocks[3].lines).toEqual(["one", "two"]);
    expect(blocks[4].lines).toEqual(["first", "second"]);
  });

  it("joins wrapped paragraph lines into one block", () => {
    const blocks = parseArticleBody("Line one\nline two\n\nNext.");
    expect(blocks).toHaveLength(2);
    expect(blocks[0].text).toBe("Line one line two");
  });

  it("treats ### as a subheading", () => {
    expect(parseArticleBody("### Detail")[0]).toMatchObject({
      type: "h3",
      text: "Detail",
    });
  });

  it("keeps stray markup as literal text instead of parsing it", () => {
    const blocks = parseArticleBody("<script>alert(1)</script>");
    expect(blocks[0].type).toBe("p");
    expect(blocks[0].text).toContain("<script>");
  });

  it("returns no blocks for empty input", () => {
    expect(parseArticleBody("")).toEqual([]);
  });
});

describe("take-action roles", () => {
  it("defines a usable role for every station in life", () => {
    const ids = ROLES.map((role) => role.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ["parent", "teacher", "leo", "child", "teen", "volunteer"]) {
      expect(ids).toContain(id);
    }
  });

  it("gives every role steps and a guardrail", () => {
    for (const role of ROLES) {
      expect(role.steps.length).toBeGreaterThanOrEqual(3);
      for (const step of role.steps) {
        expect(step.title.length).toBeGreaterThan(0);
        expect(step.body.length).toBeGreaterThan(20);
      }
      expect(role.guardrail.length).toBeGreaterThan(20);
    }
  });

  it("only links to internal paths or web URLs", () => {
    for (const role of ROLES) {
      for (const step of role.steps) {
        if (!step.href) continue;
        const ok =
          step.href.startsWith("/") ||
          step.href.startsWith("https://") ||
          step.href.startsWith("tel:");
        expect(ok, `${role.id}: ${step.href}`).toBe(true);
      }
    }
  });

  it("looks up roles by id and falls back safely", () => {
    expect(getRole("leo")?.label).toBe("Law enforcement");
    expect(getRole("nope")).toBeUndefined();
    expect(getRole(roleDefaultId())).toBeDefined();
  });
});
