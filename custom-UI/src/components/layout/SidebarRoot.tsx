import type { RenderPlan } from "../../compile/plan.js";
import type { ActionDispatcher } from "../../runtime/dispatcher.js";
import { GridRoot } from "./GridRoot.js";

export function SidebarRoot({
  plan,
  dispatcher,
}: {
  plan: RenderPlan;
  dispatcher: ActionDispatcher;
}): JSX.Element {
  if (plan.layout.kind !== "sidebar") {
    throw new Error("SidebarRoot received non-sidebar plan");
  }
  const { menu, main } = plan.layout;
  const inner: RenderPlan = { ...plan, layout: main };

  return (
    <div className="au-sidebar-root">
      <nav className="au-sidebar">
        {menu.map((item) => (
          <button
            key={item.action}
            type="button"
            className="au-sidebar-item"
            onClick={() => void dispatcher.invoke(item.action)}
          >
            {item.icon && (
              <img src={item.icon} alt="" className="au-sidebar-icon" />
            )}
            <span>{item.name}</span>
          </button>
        ))}
      </nav>
      <main className="au-sidebar-main">
        <GridRoot plan={inner} dispatcher={dispatcher} />
      </main>
    </div>
  );
}
