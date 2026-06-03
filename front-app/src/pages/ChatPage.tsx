import { CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { AgentUI, type ConversationMessage } from "agent-ui";

import { getAgentUiYaml } from "../api/agents";
import { listMessages } from "../api/conversations";
import { listKeys } from "../api/keys";
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

  // Identity of the current chat surface — also the `<AgentUI>` remount key.
  // The greeting's first message is tagged with this so it fires into exactly
  // the surface it was composed in, and is never resent when you switch
  // conversations or start a new session (the value is recomputed fresh each
  // render, so a navigated-away surface can't match a stale pending message).
  const surfaceKey = `${agentId ?? ""}:${conversationId ?? "new"}:${sessionNonce}`;

  const convRef = useRef<string | null>(null);
  convRef.current = conversationId ?? null;
  // The conversation lazily created from the greeting. We don't navigate on
  // create (keeps the live stream), so the URL — and thus `conversationId` /
  // `convRef` — stays null for it. Held in its own ref so a re-render doesn't
  // clobber it back to null; actions + data_source resolve against it. Cleared
  // when the surface changes (new session / agent / selecting a conversation).
  const createdRef = useRef<string | null>(null);
  const agentRef = useRef<string | null>(null);
  agentRef.current = agentId ?? null;

  /** The active conversation id: the URL's, else the one created this session. */
  const liveConversationId = () => convRef.current ?? createdRef.current;

  // The first message (text + attachments) from the greeting, before a
  // conversation exists. Tagged with the surface it was composed in.
  const [pendingFirst, setPendingFirst] = useState<
    { text: string; fileIds: string[]; key: string } | null
  >(null);
  const firedRef = useRef<string | null>(null);

  // Only honor a pending first-message that still belongs to this surface.
  const activeFirst =
    pendingFirst && pendingFirst.key === surfaceKey ? pendingFirst : null;

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

  // Onboarding gate: with no API key set, the agent can only echo — so block the
  // first message and prompt the user to add one. Shared cache key with Settings.
  const keysQuery = useQuery({ queryKey: ["me", "keys"], queryFn: listKeys });
  const requiresKey = keysQuery.isSuccess && (keysQuery.data?.length ?? 0) === 0;

  const bridge = useMemo(
    () =>
      new RuntimeBridge({
        getConversationId: liveConversationId,
        getAgentId: () => agentRef.current,
        onConversationCreated: (id) => {
          createdRef.current = id;
          qc.invalidateQueries({ queryKey: ["conversations"] });
        },
        canSubmit: () => null,
      }),
    // Fresh bridge per agent / conversation / new session.
    [agentId, conversationId, sessionNonce, qc],
  );

  const dispatcher = useMemo(
    () => makeDispatcher(liveConversationId),
    [agentId, conversationId, sessionNonce],
  );

  // On any surface change (select a conversation / New session), drop the
  // greeting's pending message and free the fire slot. A pending message can
  // only ever belong to a *prior* surface here (it's tagged with the surface it
  // was composed in), so clearing is always correct — and it lets a repeated
  // surface key (e.g. browser-back to `/`) fire a fresh first message again.
  useEffect(() => {
    setPendingFirst(null);
    firedRef.current = null;
    createdRef.current = null;
  }, [surfaceKey]);

  // Fire the greeting's first message into the freshly-mounted bridge exactly
  // once — but only when the chat will actually render (yaml loaded), so the
  // transcript has mounted + subscribed (child effects run before this parent
  // effect) and no early tokens are missed. Keyed by surface, so switching
  // conversations or sessions can never re-fire it.
  useEffect(() => {
    if (
      activeFirst &&
      typeof yaml === "string" &&
      firedRef.current !== activeFirst.key
    ) {
      firedRef.current = activeFirst.key;
      void bridge.onUserSubmit(activeFirst.text, {
        fileIds: activeFirst.fileIds,
      });
    }
  }, [activeFirst, yaml, bridge]);

  if (!agent) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  // Greeting / new-session empty state.
  if (!conversationId && !activeFirst) {
    return (
      <Greeting
        agent={agent}
        sessionKey={`${agentId}:${sessionNonce}`}
        requiresKey={requiresKey}
        onSend={(text, fileIds) =>
          setPendingFirst({ text, fileIds, key: surfaceKey })
        }
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
    : activeFirst
      ? [
          {
            id: "first",
            role: "user" as const,
            content: activeFirst.text,
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
        key={surfaceKey}
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
