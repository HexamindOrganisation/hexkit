import { History, MoreHorizontal } from "lucide-react";

import { AgentDropdown } from "../components/AgentDropdown";
import { useActiveAgent } from "../hooks/useActiveAgent";

/**
 * Top bar (constant chrome): agent picker on the left, the session title in
 * muted text, global actions on the right. Agent identity lives here — there
 * is no standalone page-header widget.
 */
export function Header() {
  const { conversation } = useActiveAgent();
  const title = conversation?.title ?? "New session";

  return (
    <header className="flex h-[58px] shrink-0 items-center gap-3 border-b border-border px-3">
      <AgentDropdown />
      <span className="min-w-0 flex-1 truncate text-sm text-[var(--hx-text-3,hsl(var(--muted-foreground)))]">
        {title}
      </span>
      <button
        type="button"
        className="rounded-md p-2 text-muted-foreground hover:bg-secondary"
        aria-label="History"
      >
        <History className="h-4 w-4" />
      </button>
      <button
        type="button"
        className="rounded-md p-2 text-muted-foreground hover:bg-secondary"
        aria-label="More"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>
    </header>
  );
}
