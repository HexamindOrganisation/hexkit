import type { ResolvedWidget } from "../resolve.js";
import type { FlexItem, LayoutPlan } from "./types.js";

const COLUMNS = 12;

export function compileFlex(
  widgets: ResolvedWidget[],
  direction: "row" | "column" = "column",
): Extract<LayoutPlan, { kind: "flex" }> {
  const items: FlexItem[] = widgets.map((w) => ({
    id: w.name,
    kind: "widget",
    basis: `${(Math.min(COLUMNS, Math.max(1, w.size.width)) / COLUMNS) * 100}%`,
    height: w.size.height,
  }));
  return { kind: "flex", direction, items };
}
