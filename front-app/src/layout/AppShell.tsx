import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar.js";

export function AppShell(): JSX.Element {
  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
