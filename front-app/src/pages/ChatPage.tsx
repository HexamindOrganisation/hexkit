import { CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { AgentUI, type ConversationMessage } from "agent-ui";

import { getAgentUiYaml } from "../api/agents";
import { listMessages } from "../api/conversations";
import { useActiveAgent } from "../hooks/useActiveAgent";
import { RuntimeBridge } from "../runtime/runtimeBridge";
import { makeDispatcher } from "../runtime/dispatcher";
import { Greeting } from "../components/Greeting";

/**
 * The MAIN region. Two states:
 *
 *  - **Greeting** (no conversation + nothing sent this session): a clean
 *    centered greeting + composer (the agent's widgets stay hidden, per spec).
 *  - **Chat**: mounts `<AgentUI>` with the agent's `ui.yaml` + a RuntimeBridge.
 *
 * First-message handoff: sending from the greeting sets `pendingFirst`, which
 * switches to chat. The chat mount seeds the user turn via `initialMessages` and
 * fires `bridge.onUserSubmit` exactly once (after AgentUI's transcript has
 * subscribed), so the reply streams in — no race, no remount.
 *
 * Keying: `<AgentUI>` is keyed by `agentId:conversationId:nonce`. Lazy
 * conversation-creation does NOT navigate, so the key is stable and the live
 * stream isn't torn down; selecting an existing conversation changes the key and
 * seeds its stored history; a new session (`n`) replays the greeting.
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

  // The first message (text + attachments) from the greeting, before a
  // conversation exists.
  const [pendingFirst, setPendingFirst] = useState<
    { text: string; fileIds: string[] } | null
  >(null);
  const firedRef = useRef<string | null>(null);

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

  const bridge = useMemo(
    () =>
      new RuntimeBridge({
        getConversationId: () => convRef.current,
        getAgentId: () => agentRef.current,
        onConversationCreated: (id) => {
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

  // Reset the pending first-message whenever the session/agent/conversation
  // changes (e.g. New session → greeting again; selecting an existing chat).
  useEffect(() => {
    setPendingFirst(null);
    firedRef.current = null;
  }, [agentId, conversationId, sessionNonce]);

  // Fire the greeting's first message into the freshly-mounted bridge exactly
  // once — but only when the chat will actually render (yaml loaded), so the
  // transcript has mounted + subscribed (child effects run before this parent
  // effect) and no early tokens are missed.
  useEffect(() => {
    if (
      pendingFirst &&
      typeof yaml === "string" &&
      firedRef.current !== pendingFirst.text
    ) {
      firedRef.current = pendingFirst.text;
      void bridge.onUserSubmit(pendingFirst.text, {
        fileIds: pendingFirst.fileIds,
      });
    }
  }, [pendingFirst, yaml, bridge]);

  if (!agent) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  // Greeting / new-session empty state.
  if (!conversationId && !pendingFirst) {
    return (
      <Greeting
        agent={agent}
        sessionKey={`${agentId}:${sessionNonce}`}
        onSend={(text, fileIds) => setPendingFirst({ text, fileIds })}
      />
    );
  }

  const historyPending = !!conversationId && history === undefined;
  if (yaml === undefined || historyPending) {
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

  // Seed the transcript: an existing conversation's stored messages, or the
  // greeting's first user turn (the bridge then appends the streamed reply).
  const initialMessages: ConversationMessage[] | undefined = conversationId
    ? history?.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        timestamp: Date.parse(m.created_at) || Date.now(),
      }))
    : pendingFirst
      ? [
          {
            id: "first",
            role: "user" as const,
            content: pendingFirst.text,
            timestamp: Date.now(),
          },
        ]
      : undefined;

  // The chat avatar (agent-agnostic widget) reads the agent's initial from this
  // inherited, quoted-string CSS var.
  const initial = (agent.name?.trim().charAt(0) ?? "").toUpperCase();

  return (
    <div
      className="h-full overflow-hidden"
      style={{ "--hx-assistant-initial": `"${initial}"` } as CSSProperties}
    >
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
