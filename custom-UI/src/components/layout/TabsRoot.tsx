import { useState } from "react";
import type { RenderPlan } from "../../compile/plan.js";
import type { ActionDispatcher } from "../../runtime/dispatcher.js";
import { GridRoot } from "./GridRoot.js";

export function TabsRoot({
  plan,
  dispatcher,
}: {
  plan: RenderPlan;
  dispatcher: ActionDispatcher;
}): JSX.Element {
  if (plan.layout.kind !== "tabs") {
    throw new Error("TabsRoot received non-tabs plan");
  }
  const { tabs } = plan.layout;
  const [active, setActive] = useState(tabs[0]?.id ?? "");
  const current = tabs.find((t) => t.id === active);

  return (
    <div className="au-tabs-root">
      <div className="au-tab-bar" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={t.id === active}
            className={`au-tab ${t.id === active ? "au-tab-active" : ""}`}
            onClick={() => setActive(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {current && current.content.kind === "grid" && (
        <GridRoot
          plan={{ ...plan, layout: current.content }}
          dispatcher={dispatcher}
        />
      )}
    </div>
  );
}
