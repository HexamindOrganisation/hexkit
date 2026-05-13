import { useState } from "react";
import { AgentUI, type ActionDispatcher } from "../../src";
import "../../src/styles.css";
import "../../src/shadcn.css";

import gridYaml from "./grid.yaml?raw";
import flexYaml from "./flex.yaml?raw";
import sidebarYaml from "./sidebar.yaml?raw";
import tabsYaml from "./tabs.yaml?raw";

type LayoutKey = "grid" | "flex" | "sidebar" | "tabs";

const configs: Record<LayoutKey, string> = {
  grid: gridYaml,
  flex: flexYaml,
  sidebar: sidebarYaml,
  tabs: tabsYaml,
};

// No backend, no agent. Every action just logs to the console so you can
// see what the form/buttons/menu would dispatch in a real app.
const dispatcher: ActionDispatcher = {
  async invoke(action, args) {
    // eslint-disable-next-line no-console
    console.log("[dispatch]", action, args ?? {});
  },
  has() {
    return true;
  },
};

export default function App(): JSX.Element {
  const [layout, setLayout] = useState<LayoutKey>("grid");

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <nav
        style={{
          display: "flex",
          gap: "0.5rem",
          padding: "0.75rem 1rem",
          borderBottom: "1px solid #e5e7eb",
          background: "#f9fafb",
          fontFamily: "Inter, sans-serif",
          fontSize: "0.875rem",
        }}
      >
        <strong style={{ marginRight: "0.5rem" }}>Layout:</strong>
        {(Object.keys(configs) as LayoutKey[]).map((k) => (
          <button
            key={k}
            onClick={() => setLayout(k)}
            style={{
              border: "1px solid",
              borderColor: layout === k ? "#469BE5" : "#d1d5db",
              background: layout === k ? "#469BE5" : "white",
              color: layout === k ? "white" : "#111827",
              padding: "0.25rem 0.75rem",
              borderRadius: "0.375rem",
              cursor: "pointer",
              fontWeight: 500,
            }}
          >
            {k}
          </button>
        ))}
      </nav>

      <div style={{ flex: 1, minHeight: 0 }}>
        <AgentUI
          key={layout}
          config={configs[layout]}
          dispatcher={dispatcher}
          diagnostics="overlay"
        />
      </div>
    </div>
  );
}
