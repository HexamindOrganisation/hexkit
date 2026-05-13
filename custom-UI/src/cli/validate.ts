import { readFileSync } from "node:fs";
import { parseYaml } from "../compile/parse.js";
import { resolve as resolveConfig } from "../compile/resolve.js";
import { WidgetRegistry } from "../registry/register.js";
import { builtinWidgets } from "../registry/builtin.js";
import type { Diagnostic } from "../diagnostics/types.js";

/**
 * CLI-side validation. Since there's no dispatcher in the CLI, the
 * unknown-action diagnostic is skipped — we only check shape, widget types,
 * and duplicate names.
 */
export function validateFile(path: string): {
  ok: boolean;
  diagnostics: Diagnostic[];
} {
  const text = readFileSync(path, "utf8");
  const parsed = parseYaml(text);
  if (!parsed.ok) return { ok: false, diagnostics: parsed.errors };
  const registry = new WidgetRegistry(builtinWidgets);
  const r = resolveConfig(parsed.value.data, {
    registry,
    locate: parsed.value.locate,
  });
  if (!r.ok) return { ok: false, diagnostics: r.errors };
  return { ok: true, diagnostics: [] };
}

export function formatDiagnostic(d: Diagnostic): string {
  const loc =
    d.sourceLine !== undefined
      ? ` (line ${d.sourceLine}${d.sourceCol !== undefined ? `:${d.sourceCol}` : ""})`
      : "";
  const pathStr = d.path.length > 0 ? ` at ${d.path.join(".")}` : "";
  return `${d.severity.toUpperCase()} ${d.code}${loc}: ${d.message}${pathStr}`;
}
