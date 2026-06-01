import { useMemo, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { AgentUI } from "agent-ui";

import { getAgentUiYaml } from "../api/agents";
import { useActiveAgent } from "../hooks/useActiveAgent";
import { RuntimeBridge } from "../runtime/runtimeBridge";
import { makeDispatcher } from "../runtime/dispatcher";

/**
 * The MAIN region: mounts `<AgentUI>` with the active agent's `ui.yaml` and a
 * RuntimeBridge wired to the proxy. The agent's `main_color` (theme.accent)
 * recolors the whole layout.
 *
 * Keying: `<AgentUI>` remounts on agent switch or a fresh session (the `n`
 * query param), but NOT on lazy conversation-creation — so a live stream that
 * creates its conversation mid-flight isn't torn down. `conversationId` is read
 * through a ref so the next send targets the right conversation.
 *
 * Known gap (M4): selecting an existing conversation doesn't yet replay its
 * stored messages into the transcript — the bridge only renders live runs.
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
    // Fresh bridge per agent / per new session.
    [agentId, sessionNonce, qc],
  );

  const dispatcher = useMemo(
    () => makeDispatcher(() => convRef.current),
    [agentId, sessionNonce],
  );

  if (!agent || yaml === undefined) {
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
    <div className="h-full overflow-auto">
      <AgentUI
        key={`${agentId}:${sessionNonce}`}
        config={yaml}
        dispatcher={dispatcher}
        agent={bridge}
        theme={{ mode: "dark", accent: agent.main_color }}
        diagnostics="console"
      />
    </div>
  );
}
