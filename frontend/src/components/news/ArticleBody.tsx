/**
 * Render the model's article Markdown with a small, fixed block vocabulary.
 *
 * The body is untrusted model output, so raw HTML is never inserted: everything
 * is escaped by React and only these constructs render structurally:
 * `## heading`, `### heading`, `- bullet`, `1. numbered`, blank line = paragraph,
 * and `**bold**` inside a line. Anything else stays literal text.
 */

import type { ReactNode } from "react";

interface Block {
  type: "h2" | "h3" | "p" | "ul" | "ol";
  text?: string;
  lines?: string[];
}

const INLINE_BOLD = /\*\*([^*]+)\*\*/g;

/** Split a line into escaped text and bold runs for React to render. */
export function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  const pattern = new RegExp(INLINE_BOLD);

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    nodes.push(
      <strong key={`${match.index}-bold`} className="font-bold text-foreground">
        {match[1]}
      </strong>
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

export function parseArticleBody(body: string): Block[] {
  const lines = (body || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let list: { type: "ul" | "ol"; lines: string[] } | null = null;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: "p", text: paragraph.join(" ") });
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list && list.lines.length) {
      blocks.push({ type: list.type, lines: list.lines });
    }
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trim();

    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    const heading = /^(#{2,3})\s+(.*)$/.exec(line);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push({
        type: heading[1].length === 3 ? "h3" : "h2",
        text: heading[2].trim(),
      });
      continue;
    }

    const bullet = /^[-*]\s+(.*)$/.exec(line);
    if (bullet) {
      flushParagraph();
      if (list?.type !== "ul") {
        flushList();
        list = { type: "ul", lines: [] };
      }
      list.lines.push(bullet[1].trim());
      continue;
    }

    const numbered = /^\d+[.)]\s+(.*)$/.exec(line);
    if (numbered) {
      flushParagraph();
      if (list?.type !== "ol") {
        flushList();
        list = { type: "ol", lines: [] };
      }
      list.lines.push(numbered[1].trim());
      continue;
    }

    // A heading-like "##" with no text is not a heading; keep it as prose.
    flushList();
    paragraph.push(line.replace(/^>\s*/, ""));
  }

  flushParagraph();
  flushList();
  return blocks;
}

export function ArticleBody({ body }: { body: string }) {
  const blocks = parseArticleBody(body);

  return (
    <div className="max-w-none text-[1.02rem] leading-relaxed text-text-subtle">
      {blocks.map((block, index) => {
        if (block.type === "h2") {
          return (
            <h2
              key={index}
              className="mt-8 mb-3 text-xl font-bold text-blue sm:text-2xl"
            >
              {renderInline(block.text ?? "")}
            </h2>
          );
        }
        if (block.type === "h3") {
          return (
            <h3 key={index} className="mt-6 mb-2 text-lg font-bold text-blue">
              {renderInline(block.text ?? "")}
            </h3>
          );
        }
        if (block.type === "ul" || block.type === "ol") {
          const ListTag = block.type === "ul" ? "ul" : "ol";
          return (
            <ListTag
              key={index}
              className={`my-4 space-y-2 pl-5 ${block.type === "ul" ? "list-disc" : "list-decimal"}`}
            >
              {(block.lines ?? []).map((line, lineIndex) => (
                <li key={lineIndex}>{renderInline(line)}</li>
              ))}
            </ListTag>
          );
        }
        return (
          <p key={index} className="my-4">
            {renderInline(block.text ?? "")}
          </p>
        );
      })}
    </div>
  );
}
