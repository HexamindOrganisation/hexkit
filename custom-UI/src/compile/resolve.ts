import type { Diagnostic, Result } from "../diagnostics/types.js";
import { ok, err } from "../diagnostics/types.js";
import type { WidgetRegistry } from "../registry/register.js";
import type { ActionDispatcher } from "../runtime/dispatcher.js";
import type { ComponentType } from "react";
import type { WidgetProps } from "../registry/types.js";
import type { Page } from "../schema/page.js";
import type { Position, Size } from "../schema/common.js";
import type { SourceMap } from "./parse.js";
import { PageSchema } from "../schema/page.js";
import { compileSchema } from "../schema/ajv.js";
import { ajvErrorsToDiagnostics } from "../diagnostics/ajv.js";
import { PlaceholderWidget } from "../widgets/placeholder.js";

export interface ResolvedWidget {
  id: string;
  type: string;
  name: string;
  props: unknown;
  position: Position | undefined;
  size: Size;
  tab?: string;
  component: ComponentType<WidgetProps<unknown>>;
  chromeless?: boolean;
  slot?: "main" | "footer";
}

export interface ResolvedConfig {
  page: Page;
  widgets: ResolvedWidget[];
  /** Widgets whose `type` was unknown at resolve time — rendered as placeholders. */
  unknownWidgets: { name: string; type: string }[];
  /** Warnings accumulated during resolve. Errors never reach this field — they throw via Result.err. */
  diagnostics: Diagnostic[];
}

export interface ResolveOptions {
  registry: WidgetRegistry;
  dispatcher?: ActionDispatcher;
  locate?: SourceMap;
}

// Compile the Page schema once, lazily.
let pageValidator: ReturnType<typeof compileSchema> | null = null;
function getPageValidator(): ReturnType<typeof compileSchema> {
  if (!pageValidator) pageValidator = compileSchema(PageSchema);
  return pageValidator;
}

/**
 * Stage 3: take validated raw data (still `unknown` because the union is
 * dynamic per registry) and produce a ResolvedConfig.
 *
 * - Validates `page` with PageSchema.
 * - For each widget, looks up the registered schema and validates it.
 * - Collects diagnostics for: reserved names, duplicates, unknown types,
 *   unknown actions.
 * - Unknown widget types don't drop — they become placeholder entries.
 */
export function resolve(
  raw: unknown,
  opts: ResolveOptions,
): Result<ResolvedConfig, Diagnostic[]> {
  const diagnostics: Diagnostic[] = [];

  if (typeof raw !== "object" || raw === null) {
    return err([
      {
        severity: "error",
        code: "resolve.not-object",
        message: "Config must be an object with `page` and `widgets`.",
        path: [],
      },
    ]);
  }

  const root = raw as { page?: unknown; widgets?: unknown };

  const validatePage = getPageValidator();
  const pageCandidate = structuredClone(root.page) as object;
  if (!validatePage(pageCandidate)) {
    diagnostics.push(
      ...ajvErrorsToDiagnostics(validatePage.errors, ["page"], opts.locate),
    );
    return err(diagnostics);
  }
  const page = pageCandidate as Page;

  const rawWidgets = Array.isArray(root.widgets) ? root.widgets : [];
  const resolved: ResolvedWidget[] = [];
  const unknownWidgets: { name: string; type: string }[] = [];
  const seenNames = new Set<string>();

  rawWidgets.forEach((item, idx) => {
    if (typeof item !== "object" || item === null) {
      diagnostics.push({
        severity: "error",
        code: "resolve.widget-not-object",
        message: `widgets[${idx}] is not an object`,
        path: ["widgets", idx],
        ...getLoc(opts.locate, ["widgets", idx]),
      });
      return;
    }
    const w = item as { name?: unknown; type?: unknown };
    const name = typeof w.name === "string" ? w.name : "";
    const type = typeof w.type === "string" ? w.type : "";

    if (!name) {
      diagnostics.push({
        severity: "error",
        code: "resolve.missing-name",
        message: `widgets[${idx}] is missing "name"`,
        path: ["widgets", idx],
        ...getLoc(opts.locate, ["widgets", idx]),
      });
      return;
    }
    if (!type) {
      diagnostics.push({
        severity: "error",
        code: "resolve.missing-type",
        message: `widget "${name}" is missing "type"`,
        path: ["widgets", idx, "type"],
        ...getLoc(opts.locate, ["widgets", idx, "type"]),
      });
      return;
    }

    if (seenNames.has(name)) {
      diagnostics.push({
        severity: "error",
        code: "resolve.duplicate-name",
        message: `widget name "${name}" is used more than once`,
        path: ["widgets", idx, "name"],
        ...getLoc(opts.locate, ["widgets", idx, "name"]),
      });
      return;
    }
    seenNames.add(name);

    const def = opts.registry.get(type);
    if (!def) {
      diagnostics.push({
        severity: "warning",
        code: "resolve.unknown-type",
        message: `widget "${name}" has unknown type "${type}"; rendered as placeholder`,
        path: ["widgets", idx, "type"],
        ...getLoc(opts.locate, ["widgets", idx, "type"]),
      });
      unknownWidgets.push({ name, type });
      const raw = item as { size?: Size; position?: Position; tab?: string };
      const size = raw.size ?? { width: 6, height: 120 };
      resolved.push({
        id: name,
        name,
        type,
        props: {
          name,
          type,
          reason: "Type not registered. Register with defineWidget().",
        },
        position: raw.position,
        size,
        ...(raw.tab !== undefined && { tab: raw.tab }),
        component: PlaceholderWidget as unknown as ComponentType<
          WidgetProps<unknown>
        >,
      });
      return;
    }

    const merged = def.defaults
      ? { ...def.defaults, ...(item as object) }
      : item;
    // Ajv mutates input in place (defaults / removeAdditional). Clone so the
    // caller's input isn't surprised.
    const candidate = structuredClone(merged) as object;
    if (!def.validate(candidate)) {
      diagnostics.push(
        ...ajvErrorsToDiagnostics(
          def.validate.errors,
          ["widgets", idx],
          opts.locate,
        ),
      );
      return;
    }

    const data = candidate as {
      name: string;
      type: string;
      position?: Position;
      size: Size;
      tab?: string;
    };

    resolved.push({
      id: data.name,
      name: data.name,
      type: data.type,
      props: data,
      position: data.position,
      size: data.size,
      ...(data.tab !== undefined && { tab: data.tab }),
      component: def.component,
      ...(def.chromeless && { chromeless: true }),
      ...(def.slot && def.slot !== "main" && { slot: def.slot }),
    });

    // Cross-check action names referenced anywhere in the widget props.
    if (opts.dispatcher?.has) {
      const actions = collectActionNames(data);
      for (const a of actions) {
        if (!opts.dispatcher.has(a.action)) {
          diagnostics.push({
            severity: "warning",
            code: "resolve.unknown-action",
            message: `widget "${name}" references unknown action "${a.action}"`,
            path: ["widgets", idx, ...a.path],
            ...getLoc(opts.locate, ["widgets", idx, ...a.path]),
          });
        }
      }
    }
  });

  // Cross-check page.main_menu actions.
  if (opts.dispatcher?.has && page.main_menu) {
    page.main_menu.forEach((item, idx) => {
      if (!opts.dispatcher!.has!(item.action)) {
        diagnostics.push({
          severity: "warning",
          code: "resolve.unknown-action",
          message: `main_menu[${idx}] references unknown action "${item.action}"`,
          path: ["page", "main_menu", idx, "action"],
          ...getLoc(opts.locate, ["page", "main_menu", idx, "action"]),
        });
      }
    });
  }

  const errors = diagnostics.filter((d) => d.severity === "error");
  if (errors.length > 0) return err(errors);
  return ok({ page, widgets: resolved, unknownWidgets, diagnostics });
}

function getLoc(
  locate: SourceMap | undefined,
  path: (string | number)[],
): { sourceLine?: number; sourceCol?: number } {
  const loc = locate?.(path);
  if (!loc) return {};
  return {
    ...(loc.line !== undefined && { sourceLine: loc.line }),
    ...(loc.col !== undefined && { sourceCol: loc.col }),
  };
}

/**
 * Walk a widget's validated props and collect every `action`/`submit_action`
 * string along with its path. Used for unknown-action diagnostics.
 */
function collectActionNames(
  node: unknown,
  path: (string | number)[] = [],
): { action: string; path: (string | number)[] }[] {
  const out: { action: string; path: (string | number)[] }[] = [];
  if (node === null || node === undefined) return out;
  if (Array.isArray(node)) {
    node.forEach((item, i) => out.push(...collectActionNames(item, [...path, i])));
    return out;
  }
  if (typeof node === "object") {
    for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
      if ((k === "action" || k === "submit_action") && typeof v === "string") {
        out.push({ action: v, path: [...path, k] });
      } else {
        out.push(...collectActionNames(v, [...path, k]));
      }
    }
  }
  return out;
}
