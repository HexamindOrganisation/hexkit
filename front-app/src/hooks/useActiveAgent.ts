import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";

import { listAgents, type AgentSummary } from "../api/agents";
import { listConversations, type Conversation } from "../api/conversations";

export function useAgents() {
  return useQuery({ queryKey: ["agents"], queryFn: listAgents });
}

export function useConversations() {
  return useQuery({ queryKey: ["conversations"], queryFn: listConversations });
}

/**
 * The active agent + conversation, derived purely from the URL + cached
 * queries — no extra state to keep in sync.
 *
 *   /            → agent from `?agent=`, else first in roster
 *   /c/:id       → agent from that conversation's `agent_id`
 */
export function useActiveAgent(): {
  agents: AgentSummary[];
  agent: AgentSummary | undefined;
  agentId: string | undefined;
  conversationId: string | undefined;
  conversation: Conversation | undefined;
  conversations: Conversation[];
} {
  const { id: conversationId } = useParams();
  const [sp] = useSearchParams();
  const { data: agents = [] } = useAgents();
  const { data: conversations = [] } = useConversations();

  const conversation = conversations.find((c) => c.id === conversationId);
  const agentId =
    conversation?.agent_id ?? sp.get("agent") ?? agents[0]?.id;
  const agent = agents.find((a) => a.id === agentId);

  return {
    agents,
    agent,
    agentId,
    conversationId,
    conversation,
    conversations,
  };
}
