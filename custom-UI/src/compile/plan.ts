import type { Diagnostic, Result } from "../diagnostics/types.js";
import { ok, err, hasErrors } from "../diagnostics/types.js";
import type { ResolvedWidget } from "./resolve.js";
import { resolve, type ResolveOptions } from "./resolve.js";
import { normalize } from "./normalize.js";
import { resolveTheme, type ResolvedTheme, type ThemeTokens } from "./theme.js";
import type { LayoutPlan } from "./layout/types.js";
import { compileGrid } from "./layout/grid.js";
import { compileFlex } from "./layout/flex.js";
import { compileSidebar } from "./layout/sidebar.js";
import { compileTabs } from "./layout/tabs.js";
import type { WidgetRegistry } from "../registry/register.js";
import type { ActionDispatcher } from "../runtime/dispatcher.js";
import type { SourceMap } from "./parse.js";
import type { ComponentType } from "react";
import type { WidgetProps } from "../registry/types.js";

export interface RenderPlan {
  theme: ResolvedTheme;
  layout: LayoutPlan;
  /** Widgets that participate in the layout (slot: "main"). */
  widgets: RenderPlanWidget[];
  /** Widgets pinned to the bottom of the page (slot: "footer"), in YAML order. */
  footer: RenderPlanWidget[];
  diagnostics: Diagnostic[];
}

export interface RenderPlanWidget {
  id: string;
  name: string;
  type: string;
  props: unknown;
  height: number | "auto";
  component: ComponentType<WidgetProps<unknown>>;
  chromeless?: boolean;
  slot?: "main" | "footer";
}

export interface CompileOptions {
  registry: WidgetRegistry;
  dispatcher?: ActionDispatcher;
  locate?: SourceMap;
  themeOverride?: Partial<ThemeTokens>;
}

/**
 * Stage 5: compile a ResolvedConfig into a RenderPlan.
 * Takes diagnostics from earlier stages and appends layout diagnostics.
 */
export function compilePlan(
  raw: unknown,
  opts: CompileOptions,
): Result<RenderPlan, Diagnostic[]> {
  const resolveOpts: ResolveOptions = {
    registry: opts.registry,
    ...(opts.dispatcher && { dispatcher: opts.dispatcher }),
    ...(opts.locate && { locate: opts.locate }),
  };
  const r = resolve(raw, resolveOpts);
  if (!r.ok) return r;

  const diagnostics: Diagnostic[] = [...r.value.diagnostics];
  const resolved = normalize(r.value);
  const theme = resolveTheme(resolved.page, opts.themeOverride ?? {});

  // Footer-slot widgets render outside the layout, pinned to the page
  // bottom, so we don't pass them to the layout compiler.
  const mainWidgets = resolved.widgets.filter((w) => w.slot !== "footer");
  const footerWidgets = resolved.widgets.filter((w) => w.slot === "footer");

  let layout: LayoutPlan;
  const lt = resolved.page.layout_type;
  if (lt === "grid") {
    const g = compileGrid(mainWidgets, diagnostics);
    layout = { kind: "grid", template: g.template, cells: g.cells };
  } else if (lt === "flex") {
    layout = compileFlex(mainWidgets, "column");
  } else if (lt === "sidebar") {
    layout = compileSidebar(resolved.page, mainWidgets, diagnostics);
  } else {
    layout = compileTabs(mainWidgets, diagnostics);
  }

  const plan: RenderPlan = {
    theme,
    layout,
    widgets: mainWidgets.map(toPlanWidget),
    footer: footerWidgets.map(toPlanWidget),
    diagnostics,
  };

  if (hasErrors(diagnostics)) return err(diagnostics);
  return ok(plan);
}

function toPlanWidget(w: ResolvedWidget): RenderPlanWidget {
  return {
    id: w.id,
    name: w.name,
    type: w.type,
    props: w.props,
    height: w.size.height,
    component: w.component,
    ...(w.chromeless && { chromeless: true }),
    ...(w.slot && w.slot !== "main" && { slot: w.slot }),
  };
}
