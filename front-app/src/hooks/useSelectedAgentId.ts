import { useMatch, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { listAgents } from "../api/agents";
import { Conversation, listConversations } from "../api/conversations";


/**
 * The "currently-selected agent" the rest of the app cares about (header
 * dropdown label, sidebar's New-chat link, ChatPage submit target).
 *
 * Resolution rules:
 *   - On `/c/:id`: locked to the conversation row's `agent_id` (read from the
 *     cached conversations list, so no extra request).
 *   - On `/?agent=X`: read from the URL search param.
 *   - Otherwise: fall back to the first agent the runtime advertises.
 *
 * Returns `{agentId, locked}` — `locked` is true on conversation routes so
 * the header can disable the dropdown.
 */
export function useSelectedAgentId(): {
  agentId: string | null;
  locked: boolean;
} {
  const convMatch = useMatch("/c/:id");
  const [searchParams] = useSearchParams();

  const agents = useQuery({ queryKey: ["agents"], queryFn: listAgents });
  const conversations = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
    // Only needed if we're on a conversation route, but cheap to keep warm
    // since the sidebar holds it too.
    enabled: convMatch !== null || true,
  });

  if (convMatch !== null) {
    const conv = (conversations.data ?? []).find(
      (c: Conversation) => c.id === convMatch.params.id,
    );
    return { agentId: conv?.agent_id ?? null, locked: true };
  }

  const fromUrl = searchParams.get("agent");
  if (fromUrl) return { agentId: fromUrl, locked: false };

  // Fallback: first agent the runtime lists. Stable as long as the runtime
  // discovers agents in directory order.
  const first = agents.data?.[0]?.agent_id ?? null;
  return { agentId: first, locked: false };
}
