import {
  parseDocument,
  LineCounter,
  isMap,
  isSeq,
  isScalar,
  type Document,
  type Node,
} from "yaml";
import type { Diagnostic, Result } from "../diagnostics/types.js";
import { ok, err } from "../diagnostics/types.js";

export type SourceMap = (
  path: (string | number)[],
) => { line?: number; col?: number } | undefined;

export type ParseResult = {
  data: unknown;
  locate: SourceMap;
};

/**
 * Parse YAML text into JSON data, preserving a `locate(path)` function that
 * returns the source line/column for any JSON path into the document.
 */
export function parseYaml(source: string): Result<ParseResult, Diagnostic[]> {
  const lc = new LineCounter();
  let doc: Document.Parsed;
  try {
    doc = parseDocument(source, { lineCounter: lc, prettyErrors: false });
  } catch (e) {
    return err([
      {
        severity: "error",
        code: "yaml.parse",
        message: e instanceof Error ? e.message : String(e),
        path: [],
      },
    ]);
  }

  if (doc.errors.length > 0) {
    return err(
      doc.errors.map((yErr) => {
        const pos = yErr.linePos?.[0];
        return {
          severity: "error" as const,
          code: "yaml.parse",
          message: yErr.message,
          path: [],
          ...(pos && { sourceLine: pos.line, sourceCol: pos.col }),
        };
      }),
    );
  }

  const data = doc.toJS({ maxAliasCount: 100 }) ?? null;
  const locate: SourceMap = (path) => locateInDoc(doc, lc, path);

  return ok({ data, locate });
}

function locateInDoc(
  doc: Document.Parsed,
  lc: LineCounter,
  path: (string | number)[],
): { line?: number; col?: number } | undefined {
  const node = doc.getIn(path, true) as Node | undefined;
  if (!node || (!isScalar(node) && !isMap(node) && !isSeq(node))) {
    if (path.length === 0) return undefined;
    return locateInDoc(doc, lc, path.slice(0, -1));
  }
  const range = node.range;
  if (!range) return undefined;
  const pos = lc.linePos(range[0]);
  return { line: pos.line, col: pos.col };
}
