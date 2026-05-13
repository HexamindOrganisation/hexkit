import type { ErrorObject } from "ajv";
import type { Diagnostic } from "./types.js";

/**
 * Map Ajv validation errors onto Diagnostic[]. `basePath` is prepended to each
 * error's instancePath so callers (e.g. resolve.ts) can scope errors under the
 * widget's index in the config.
 */
export function ajvErrorsToDiagnostics(
  errors: ErrorObject[] | null | undefined,
  basePath: (string | number)[] = [],
  locate?: (path: (string | number)[]) => { line?: number; col?: number } | undefined,
): Diagnostic[] {
  if (!errors) return [];
  return errors.map((e) => {
    const tail = e.instancePath
      .split("/")
      .filter(Boolean)
      .map((seg) => {
        const decoded = seg.replace(/~1/g, "/").replace(/~0/g, "~");
        return /^\d+$/.test(decoded) ? Number(decoded) : decoded;
      });
    const path = [...basePath, ...tail];
    const loc = locate?.(path);
    return {
      severity: "error" as const,
      code: `ajv.${e.keyword}`,
      message: formatMessage(e),
      path,
      ...(loc?.line !== undefined && { sourceLine: loc.line }),
      ...(loc?.col !== undefined && { sourceCol: loc.col }),
    };
  });
}

function formatMessage(e: ErrorObject): string {
  if (e.keyword === "required") {
    const p = e.params as { missingProperty: string };
    return `missing required property "${p.missingProperty}"`;
  }
  if (e.keyword === "additionalProperties") {
    const p = e.params as { additionalProperty: string };
    return `unexpected property "${p.additionalProperty}"`;
  }
  if (e.keyword === "enum") {
    const p = e.params as { allowedValues: unknown[] };
    return `must be one of: ${p.allowedValues.map((v) => JSON.stringify(v)).join(", ")}`;
  }
  if (e.keyword === "const") {
    const p = e.params as { allowedValue: unknown };
    return `must be ${JSON.stringify(p.allowedValue)}`;
  }
  return e.message ?? "validation error";
}
