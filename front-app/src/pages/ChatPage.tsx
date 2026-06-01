import { useMemo, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { AgentUI, type ConversationMessage } from "agent-ui";

import { getAgentUiYaml } from "../api/agents";
import { listMessages } from "../api/conversations";
import { useActiveAgent } from "../hooks/useActiveAgent";
import { RuntimeBridge } from "../runtime/runtimeBridge";
import { makeDispatcher } from "../runtime/dispatcher";

/**
 * The MAIN region: mounts `<AgentUI>` with the active agent's `ui.yaml` and a
 * RuntimeBridge wired to the proxy. The agent's `main_color` (theme.accent)
 * recolors the whole layout.
 *
 * Keying: `<AgentUI>` is keyed by `agentId:conversationId:nonce`. It remounts on
 * agent switch, conversation select (→ seeds that conversation's stored
 * messages), or a fresh session (`n` query param) — but NOT on lazy
 * conversation-creation, because `onConversationCreated` does not navigate (the
 * URL stays on `/`, so `conversationId` and the key are unchanged), keeping the
 * in-flight stream alive. `conversationId` is read through a ref so the next
 * send targets the right conversation.
 */
export function ChatPage() {
  const { agent, agentId, conversationId } = useActiveAgent();
  const [sp] = useSearchParams();
  const qc = useQueryClient();
  const sessionNonce = sp.get("n") ?? "0";

  const convRef = useRef<string | null>(null);
  convRef.current = conversationId ?? null;
  const agentRef = useRef<string | null>(null);
  agentRef.current = agentId ?? null;

  const { data: yaml } = useQuery({
    queryKey: ["ui", agentId],
    enabled: !!agentId,
    queryFn: () => getAgentUiYaml(agentId!),
  });

  // Stored messages for an existing conversation — seed the transcript on select.
  const { data: history } = useQuery({
    queryKey: ["messages", conversationId],
    enabled: !!conversationId,
    queryFn: () => listMessages(conversationId!),
  });

  const initialMessages: ConversationMessage[] | undefined = useMemo(() => {
    if (!history) return undefined;
    return history.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      timestamp: Date.parse(m.created_at) || Date.now(),
    }));
  }, [history]);

  const bridge = useMemo(
    () =>
      new RuntimeBridge({
        getConversationId: () => convRef.current,
        getAgentId: () => agentRef.current,
        onConversationCreated: (id) => {
          // Track the new id for subsequent sends and surface it in the
          // sidebar. We deliberately don't navigate mid-turn — that would
          // remount AgentUI and drop the in-flight stream.
          convRef.current = id;
          qc.invalidateQueries({ queryKey: ["conversations"] });
        },
        canSubmit: () => null,
      }),
    // Fresh bridge per agent / conversation / new session.
    [agentId, conversationId, sessionNonce, qc],
  );

  const dispatcher = useMemo(
    () => makeDispatcher(() => convRef.current),
    [agentId, conversationId, sessionNonce],
  );

  // Wait for history too when a conversation is selected, so the transcript
  // seeds in one mount rather than flashing empty then filling.
  const historyPending = !!conversationId && history === undefined;

  if (!agent || yaml === undefined || historyPending) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }
  if (yaml === null) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        {agent.name} ships no ui.yaml.
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden">
      <AgentUI
        key={`${agentId}:${conversationId ?? "new"}:${sessionNonce}`}
        config={yaml}
        dispatcher={dispatcher}
        agent={bridge}
        theme={{ mode: "dark", accent: agent.main_color }}
        {...(initialMessages && { initialMessages })}
        diagnostics="console"
      />
    </div>
  );
}
