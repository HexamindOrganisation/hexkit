import { useNavigate } from "react-router-dom";
import { PanelLeftClose, PanelLeftOpen, Plus, Settings } from "lucide-react";

import { useActiveAgent } from "../hooks/useActiveAgent";
import { AgentGlyph } from "../components/AgentGlyph";

/**
 * The constant left chrome:
 *  - brand + "New session"
 *  - shared conversation history (ALL agents), each row prefixed with its
 *    agent's colored glyph; selecting one switches to that agent + conversation
 *  - a minimal workspace label, user footer
 */
export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const navigate = useNavigate();
  const { agents, agentId, conversationId, conversations } = useActiveAgent();

  const colorFor = (id: string) =>
    agents.find((a) => a.id === id)?.main_color ?? "#6e7177";

  return (
    <aside
      className="flex h-full flex-col border-r border-border bg-[hsl(var(--background))]"
      style={{
        width: collapsed ? 56 : 264,
        background: "var(--hx-bg-2, hsl(var(--background)))",
        transition: "width 0.18s ease",
      }}
    >
      {/* Brand + collapse */}
      <div className="flex items-center justify-between px-3 py-3">
        {!collapsed && (
          <span className="select-none px-1 text-[15px] tracking-tight">
            Hexa<span className="font-bold">UI</span>
          </span>
        )}
        <button
          type="button"
          onClick={onToggle}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-secondary"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* New session */}
      <div className="px-2">
        <button
          type="button"
          onClick={() => navigate(`/?agent=${agentId ?? ""}&n=${Date.now()}`)}
          className="flex w-full items-center gap-2 rounded-md border border-border px-2.5 py-2 text-sm hover:bg-secondary"
        >
          <Plus className="h-4 w-4 shrink-0" />
          {!collapsed && <span>New session</span>}
        </button>
      </div>

      {/* Shared conversation history */}
      <nav className="mt-3 min-h-0 flex-1 overflow-y-auto px-2">
        {!collapsed && (
          <div className="px-1 pb-1 font-mono text-[11px] uppercase tracking-[0.05em] text-[var(--hx-text-3,hsl(var(--muted-foreground)))]">
            History
          </div>
        )}
        <ul className="space-y-0.5">
          {conversations.map((c) => {
            const active = c.id === conversationId;
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => navigate(`/c/${c.id}`)}
                  className={[
                    "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm",
                    active ? "bg-secondary" : "hover:bg-secondary/60",
                  ].join(" ")}
                  title={c.title ?? "Untitled"}
                >
                  <AgentGlyph
                    color={colorFor(c.agent_id)}
                    name={c.agent_id}
                    size={18}
                  />
                  {!collapsed && (
                    <span className="truncate text-[13.5px] text-foreground/90">
                      {c.title ?? "Untitled session"}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* User footer + settings */}
      <div className="flex items-center gap-2 border-t border-border px-3 py-3">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-secondary text-xs font-semibold">
          D
        </span>
        {!collapsed && (
          <span className="flex-1 truncate text-sm text-muted-foreground">
            dev01
          </span>
        )}
        <button
          type="button"
          onClick={() => navigate("/settings")}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-secondary"
          aria-label="Settings"
          title="Settings"
        >
          <Settings className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
}
