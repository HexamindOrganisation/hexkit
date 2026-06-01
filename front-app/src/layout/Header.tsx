import { useMatch, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Menu } from "lucide-react";

import { Conversation, listConversations } from "../api/conversations";
import { AgentDropdown } from "../components/AgentDropdown";
import { useSelectedAgentId } from "../hooks/useSelectedAgentId";

import { UserMenu } from "./UserMenu";


/**
 * Top bar. Houses the brand, conversation title (when applicable), agent
 * dropdown (locked on `/c/:id`, editable on `/`), and the user menu.
 */
export function Header({ onToggleSidebar }: { onToggleSidebar: () => void }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const convMatch = useMatch("/c/:id");
  const settingsMatch = useMatch("/settings");
  const conversations = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
  });
  const { agentId, locked } = useSelectedAgentId();

  const activeConv: Conversation | undefined =
    convMatch !== null
      ? (conversations.data ?? []).find((c) => c.id === convMatch.params.id)
      : undefined;

  function onAgentChange(next: string) {
    if (locked) return; // shouldn't happen — dropdown is disabled
    // Stay on /, just update the search param so the chat page picks it up.
    const sp = new URLSearchParams(searchParams);
    sp.set("agent", next);
    setSearchParams(sp, { replace: true });
    // If the user is on /settings, jump back to / so the change is visible.
    if (settingsMatch) navigate(`/?${sp.toString()}`);
  }

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-background px-3">
      <button
        onClick={onToggleSidebar}
        className="rounded p-1 hover:bg-muted md:hidden"
        aria-label="Toggle sidebar"
      >
        <Menu className="h-4 w-4" />
      </button>
      <div className="text-sm font-semibold tracking-tight">Platform</div>

      <div className="flex-1 truncate text-sm text-muted-foreground">
        {activeConv?.title ?? (settingsMatch ? "" : "New chat")}
      </div>

      {!settingsMatch && (
        <AgentDropdown
          value={agentId}
          onChange={onAgentChange}
          disabled={locked}
        />
      )}

      <UserMenu />
    </header>
  );
}
