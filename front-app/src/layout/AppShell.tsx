import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";

import { useActiveAgent } from "../hooks/useActiveAgent";
import { accentVars, hexToHslTriplet } from "../lib/color";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

/**
 * The constant HexaUI chrome: a folding sidebar + top bar wrapping the MAIN
 * region (`<AgentUI>`, rendered by ChatPage via the Outlet). The active agent's
 * `main_color` sets the accent CSS vars at the shell root, so the whole product
 * — sidebar glyphs, picker, composer send — tints from that one variable.
 */
export function AppShell() {
  const { agent } = useActiveAgent();
  const [collapsed, setCollapsed] = useState(false);
  const accent = agent?.main_color ?? "#3f9d94";

  // Mirror the accent onto <html> so portaled UI (menus rendered on
  // document.body, outside this subtree) still tints to the active agent.
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--accent-color", accent);
    const triplet = hexToHslTriplet(accent);
    if (triplet) {
      root.style.setProperty("--primary", triplet);
      root.style.setProperty("--ring", triplet);
    }
  }, [accent]);

  return (
    <div
      className="flex h-full overflow-hidden bg-background text-foreground"
      style={accentVars(accent)}
    >
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
