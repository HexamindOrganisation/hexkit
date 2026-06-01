import { useState } from "react";
import { Outlet } from "react-router-dom";

import { useSelectedAgentId } from "../hooks/useSelectedAgentId";

import { Header } from "./Header";
import { Sidebar } from "./Sidebar";


/** Private-route chrome: header + sidebar + main pane. */
export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { agentId } = useSelectedAgentId();

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <Header onToggleSidebar={() => setSidebarOpen((v) => !v)} />
      <div className="flex flex-1 overflow-hidden">
        <aside
          className={
            // Persistent on md+, slides in on smaller viewports.
            "border-r border-border bg-muted/20 " +
            (sidebarOpen
              ? "absolute inset-y-12 left-0 z-10 w-72 md:static md:w-64"
              : "hidden md:block md:w-64")
          }
        >
          <Sidebar
            currentAgentId={agentId}
            onClose={() => setSidebarOpen(false)}
          />
        </aside>
        <main className="flex-1 overflow-y-auto">
          {/* OnboardingBanner inserts itself here in Phase F4 */}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
