import type { ReactNode } from "react";
import { cn } from "./utils.js";

/**
 * Safe markdown renderer. Returns React nodes only — never raw HTML — so
 * React's text-escaping is the security boundary. Any embedded HTML in the
 * source is treated as literal text. Links are URL-scheme validated.
 *
 * Shared by the `markdown` widget and the `ai-response` transcript so assistant
 * prose renders headings / code / lists / links consistently.
 */
export function renderMarkdown(src: string): ReactNode {
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i]!;

    if (line.trim() === "") {
      i++;
      continue;
    }

    // Fenced code block: ```lang ... ```
    const fence = line.match(/^```(\w*)\s*$/);
    if (fence) {
      const lang = fence[1] ?? "";
      const code: string[] = [];
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i]!)) {
        code.push(lines[i]!);
        i++;
      }
      if (i < lines.length) i++;
      blocks.push(
        <pre
          key={key++}
          className="overflow-auto rounded-md bg-muted p-3 text-xs"
        >
          <code data-language={lang || undefined}>{code.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    // ATX heading: #..###### text
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      const level = heading[1]!.length;
      const text = heading[2]!.trim();
      const sizes = [
        "text-2xl font-semibold",
        "text-xl font-semibold",
        "text-lg font-semibold",
        "text-base font-semibold",
        "text-sm font-semibold",
        "text-sm font-semibold uppercase tracking-wide",
      ];
      const Tag = `h${level}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
      blocks.push(
        <Tag key={key++} className={cn("mt-4 mb-2", sizes[level - 1])}>
          {renderInline(text)}
        </Tag>,
      );
      i++;
      continue;
    }

    // Horizontal rule
    if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      blocks.push(<hr key={key++} className="my-3 border-border" />);
      i++;
      continue;
    }

    // Blockquote
    if (/^>\s?/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i]!)) {
        buf.push(lines[i]!.replace(/^>\s?/, ""));
        i++;
      }
      blocks.push(
        <blockquote
          key={key++}
          className="my-2 border-l-2 border-border pl-3 text-muted-foreground"
        >
          {renderInline(buf.join(" "))}
        </blockquote>,
      );
      continue;
    }

    // Lists (unordered or ordered)
    const ulMatch = line.match(/^[-*+]\s+(.*)$/);
    const olMatch = line.match(/^\d+\.\s+(.*)$/);
    if (ulMatch || olMatch) {
      const ordered = !!olMatch;
      const items: string[] = [];
      const itemRe = ordered ? /^\d+\.\s+(.*)$/ : /^[-*+]\s+(.*)$/;
      while (i < lines.length) {
        const m = lines[i]!.match(itemRe);
        if (!m) break;
        items.push(m[1]!);
        i++;
      }
      const listItems = items.map((it, idx) => (
        <li key={idx}>{renderInline(it)}</li>
      ));
      blocks.push(
        ordered ? (
          <ol key={key++} className="my-2 list-decimal space-y-1 pl-6">
            {listItems}
          </ol>
        ) : (
          <ul key={key++} className="my-2 list-disc space-y-1 pl-6">
            {listItems}
          </ul>
        ),
      );
      continue;
    }

    // Paragraph: collapse consecutive non-blank, non-special lines.
    const para: string[] = [line];
    i++;
    while (i < lines.length) {
      const l = lines[i]!;
      if (
        l.trim() === "" ||
        /^```/.test(l) ||
        /^#{1,6}\s+/.test(l) ||
        /^>\s?/.test(l) ||
        /^[-*+]\s+/.test(l) ||
        /^\d+\.\s+/.test(l) ||
        /^(-{3,}|\*{3,}|_{3,})\s*$/.test(l)
      ) {
        break;
      }
      para.push(l);
      i++;
    }
    blocks.push(
      <p key={key++} className="my-2 first:mt-0 last:mb-0">
        {renderInline(para.join(" "))}
      </p>,
    );
  }

  return blocks;
}

/**
 * Inline parser: handles `code`, **bold**, *italic*, [text](url).
 * Operates on already-text strings; emits React nodes only.
 */
function renderInline(text: string): ReactNode {
  const out: ReactNode[] = [];
  let key = 0;
  let rest = text;

  const patterns: { re: RegExp; build: (m: RegExpExecArray) => ReactNode }[] = [
    {
      re: /`([^`\n]+)`/,
      build: (m) => (
        <code
          key={key++}
          className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]"
        >
          {m[1]}
        </code>
      ),
    },
    {
      re: /\*\*([^*\n]+)\*\*/,
      build: (m) => (
        <strong key={key++} className="font-semibold">
          {renderInline(m[1]!)}
        </strong>
      ),
    },
    {
      re: /\*([^*\n]+)\*/,
      build: (m) => (
        <em key={key++} className="italic">
          {renderInline(m[1]!)}
        </em>
      ),
    },
    {
      re: /\[([^\]\n]+)\]\(([^)\s]+)\)/,
      build: (m) => {
        const safe = sanitizeUrl(m[2]!);
        if (!safe) {
          return <span key={key++}>{m[1]}</span>;
        }
        return (
          <a
            key={key++}
            href={safe}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="underline underline-offset-2 hover:text-primary"
          >
            {renderInline(m[1]!)}
          </a>
        );
      },
    },
  ];

  while (rest.length > 0) {
    let bestIdx = -1;
    let bestMatch: RegExpExecArray | null = null;
    let bestPattern: (typeof patterns)[number] | null = null;

    for (const p of patterns) {
      const m = p.re.exec(rest);
      if (m && (bestMatch === null || m.index < bestIdx)) {
        bestIdx = m.index;
        bestMatch = m;
        bestPattern = p;
      }
    }

    if (!bestMatch || !bestPattern) {
      out.push(rest);
      break;
    }

    if (bestIdx > 0) out.push(rest.slice(0, bestIdx));
    out.push(bestPattern.build(bestMatch));
    rest = rest.slice(bestIdx + bestMatch[0].length);
  }

  return out;
}

/**
 * Returns the URL only if it uses an allow-listed scheme, or is a relative
 * URL / fragment / mailto. Returns null for `javascript:`, `data:`, `vbscript:`,
 * `file:`, or any other scheme — those are treated as label-only by the caller.
 */
function sanitizeUrl(url: string): string | null {
  const trimmed = url.trim();
  if (!trimmed) return null;
  if (
    trimmed.startsWith("/") ||
    trimmed.startsWith("#") ||
    trimmed.startsWith("?") ||
    trimmed.startsWith("./") ||
    trimmed.startsWith("../")
  ) {
    return trimmed;
  }
  const schemeMatch = trimmed.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/);
  if (!schemeMatch) {
    return trimmed;
  }
  const scheme = schemeMatch[1]!.toLowerCase();
  if (scheme === "http" || scheme === "https" || scheme === "mailto") {
    return trimmed;
  }
  return null;
}
