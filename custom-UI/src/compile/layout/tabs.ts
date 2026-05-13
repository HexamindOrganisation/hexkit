import type { ResolvedWidget } from "../resolve.js";
import type { Diagnostic } from "../../diagnostics/types.js";
import type { LayoutPlan } from "./types.js";
import { compileGrid } from "./grid.js";

/**
 * Group widgets by their `tab` field. Widgets without a tab form a default
 * tab labeled "Main". Each tab's contents are compiled as a grid.
 */
export function compileTabs(
  widgets: ResolvedWidget[],
  diagnostics: Diagnostic[],
): Extract<LayoutPlan, { kind: "tabs" }> {
  const groups = new Map<string, ResolvedWidget[]>();
  for (const w of widgets) {
    const tab = w.tab ?? "Main";
    const arr = groups.get(tab) ?? [];
    arr.push(w);
    groups.set(tab, arr);
  }
  const tabs = Array.from(groups.entries()).map(([label, ws]) => ({
    id: slug(label),
    label,
    content: (() => {
      const g = compileGrid(ws, diagnostics);
      const plan: LayoutPlan = {
        kind: "grid",
        template: g.template,
        cells: g.cells,
      };
      return plan;
    })(),
  }));
  return {
    kind: "tabs",
    tabs,
    persistent: [],
  };
}

function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}
