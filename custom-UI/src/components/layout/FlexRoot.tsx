import type { RenderPlan } from "../../compile/plan.js";
import { WidgetHost } from "../WidgetHost.js";
import type { ActionDispatcher } from "../../runtime/dispatcher.js";

export function FlexRoot({
  plan,
  dispatcher,
}: {
  plan: RenderPlan;
  dispatcher: ActionDispatcher;
}): JSX.Element {
  if (plan.layout.kind !== "flex") {
    throw new Error("FlexRoot received non-flex plan");
  }
  const { items, direction } = plan.layout;
  const widgetsById = new Map(plan.widgets.map((w) => [w.id, w]));

  return (
    <div
      className="au-flex-root"
      style={{
        display: "flex",
        flexDirection: direction,
        flexWrap: "wrap",
        gap: "var(--au-space-3)",
      }}
    >
      {items.map((it) => {
        if (it.kind !== "widget") return null;
        const w = widgetsById.get(it.id);
        if (!w) return null;
        return (
          <WidgetHost
            key={it.id}
            widget={w}
            dispatcher={dispatcher}
            style={{ flexBasis: it.basis, flexGrow: 0, flexShrink: 1 }}
          />
        );
      })}
    </div>
  );
}
