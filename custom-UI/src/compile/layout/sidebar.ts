import type { ResolvedWidget } from "../resolve.js";
import type { Diagnostic } from "../../diagnostics/types.js";
import type { Page } from "../../schema/page.js";
import type { LayoutPlan } from "./types.js";
import { compileGrid } from "./grid.js";

export function compileSidebar(
  page: Page,
  widgets: ResolvedWidget[],
  diagnostics: Diagnostic[],
): Extract<LayoutPlan, { kind: "sidebar" }> {
  const g = compileGrid(widgets, diagnostics);
  return {
    kind: "sidebar",
    menu: page.main_menu ?? [],
    main: { kind: "grid", template: g.template, cells: g.cells },
  };
}
