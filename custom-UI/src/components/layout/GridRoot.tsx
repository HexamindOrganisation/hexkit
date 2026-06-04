import type { RenderPlan } from "../../compile/plan.js";
import type { GridCell, GridTemplate } from "../../compile/layout/types.js";
import { WidgetHost } from "../WidgetHost.js";
import type { ActionDispatcher } from "../../runtime/dispatcher.js";

export function GridRoot({
  plan,
  dispatcher,
}: {
  plan: RenderPlan;
  dispatcher: ActionDispatcher;
}): JSX.Element {
  if (plan.layout.kind !== "grid") {
    throw new Error("GridRoot received non-grid layout plan");
  }
  const { template, cells } = plan.layout;
  const widgetsById = new Map(plan.widgets.map((w) => [w.id, w]));

  return (
    <div
      className="au-grid-root"
      style={gridStyle(template)}
    >
      {cells.map((cell) => renderCell(cell, widgetsById, dispatcher))}
    </div>
  );
}

export function gridStyle(t: GridTemplate): React.CSSProperties {
  return {
    display: "grid",
    gridTemplateColumns: `repeat(${t.columns}, minmax(0, 1fr))`,
    // `auto` (not `min-content`): a row track must grow to contain its widget's
    // explicit height (e.g. a 420px transcript). `min-content` sizes the track
    // to the content minimum and ignores the item height, so a tall widget
    // overflows its track and overlaps the next row.
    gridAutoRows: "auto",
    gap: t.gap,
  };
}

function renderCell(
  cell: GridCell,
  widgetsById: Map<string, import("../../compile/plan.js").RenderPlanWidget>,
  dispatcher: ActionDispatcher,
): JSX.Element | null {
  const style: React.CSSProperties = {
    gridColumn: `${cell.colStart} / span ${cell.colSpan}`,
    gridRow: `${cell.rowStart} / span ${cell.rowSpan}`,
  };
  if (cell.kind === "widget") {
    const w = widgetsById.get(cell.id);
    if (!w) return null;
    return <WidgetHost key={cell.id} widget={w} dispatcher={dispatcher} style={style} />;
  }
  return null;
}
