import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown } from "lucide-react";

import { useActiveAgent } from "../hooks/useActiveAgent";
import { AgentGlyph } from "./AgentGlyph";

/**
 * Top-bar agent picker. Shows the active agent (glyph + name) and opens a menu
 * of the roster. Selecting an agent starts a fresh session with it
 * (`/?agent=<id>`), which recolors the whole product to that agent's hue.
 */
export function AgentDropdown() {
  const navigate = useNavigate();
  const { agents, agent } = useActiveAgent();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  if (!agent) return null;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-secondary"
      >
        <AgentGlyph color={agent.main_color} name={agent.name} size={22} />
        <span className="text-sm font-semibold">{agent.name}</span>
        <ChevronDown className="h-4 w-4 text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-72 overflow-hidden rounded-lg border border-border bg-popover py-1 shadow-xl">
          {agents.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => {
                setOpen(false);
                navigate(`/?agent=${a.id}`);
              }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-left hover:bg-secondary"
            >
              <AgentGlyph color={a.main_color} name={a.name} size={24} />
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">
                  {a.name}
                </span>
                <span className="block truncate text-xs text-muted-foreground">
                  {a.role}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
