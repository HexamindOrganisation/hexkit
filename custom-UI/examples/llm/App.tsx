import { AgentUI, type ActionDispatcher, type AgentBridge } from "../../src";
import type { AgentEvent } from "../../src/runtime/agentBridge";
import "../../src/styles.css";
import "../../src/shadcn.css";
import configText from "./config.yaml?raw";

const API = "http://localhost:8000";

let currentConversationId: string | null = null;
const conversationLog: { role: "user" | "assistant"; content: string }[] = [];

// Subscribers interested in LLM usage metrics. Notified after every chat
// request finishes so the metrics strip refreshes live.
const metricsSubs = new Set<(d: unknown) => void>();

async function fetchMetrics(): Promise<unknown> {
  const res = await fetch(`${API}/metrics`);
  if (!res.ok) throw new Error(`get_metrics: ${res.status}`);
  return res.json();
}

async function notifyMetricsChanged(): Promise<void> {
  if (metricsSubs.size === 0) return;
  try {
    const data = await fetchMetrics();
    metricsSubs.forEach((cb) => cb(data));
  } catch {
    // best-effort
  }
}

async function createConversation(): Promise<{ id: string }> {
  const res = await fetch(`${API}/conversations`, { method: "POST" });
  if (!res.ok) throw new Error(`create_conversation: ${res.status}`);
  const summary = await res.json();
  currentConversationId = summary.id;
  conversationLog.length = 0;
  return summary;
}

const dispatcher: ActionDispatcher = {
  async invoke(action) {
    switch (action) {
      case "refresh_data":
      case "open_settings":
      case "delete_all":
        alert(action);
        return;
      case "get_metrics":
        return fetchMetrics();
      default:
        return;
    }
  },
  subscribe(action, _args, onData, onError) {
    if (action === "get_metrics") {
      metricsSubs.add(onData);
      fetchMetrics()
        .then((d) => onData(d))
        .catch((e) => onError?.(e));
      return () => {
        metricsSubs.delete(onData);
      };
    }
    return () => {};
  },
  has() {
    return true;
  },
};

let lastEmit: ((event: AgentEvent) => void) | null = null;

const agent: AgentBridge = {
  async onUserSubmit(text) {
    if (!currentConversationId) {
      await createConversation();
    }
    conversationLog.push({ role: "user", content: text });
    const messageId = `reply-${Date.now()}`;
    lastEmit?.({ kind: "status", state: "thinking" });
    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: conversationLog,
          conversation_id: currentConversationId,
        }),
      });
      if (!res.ok || !res.body) throw new Error(`chat: ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let full = "";
      let firstChunk = true;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        if (firstChunk) {
          lastEmit?.({ kind: "status", state: "responding" });
          firstChunk = false;
        }
        full += chunk;
        lastEmit?.({ kind: "token", text: chunk, messageId });
      }
      conversationLog.push({ role: "assistant", content: full });
      lastEmit?.({
        kind: "message",
        messageId,
        role: "assistant",
        content: full,
      });
      lastEmit?.({ kind: "status", state: "idle" });
      // Token / cost / latency totals were updated server-side.
      await notifyMetricsChanged();
    } catch (err) {
      lastEmit?.({
        kind: "error",
        message: err instanceof Error ? err.message : String(err),
      });
      lastEmit?.({ kind: "status", state: "idle" });
    }
  },
  subscribeAgentOutput(cb) {
    lastEmit = cb;
    return () => {
      lastEmit = null;
    };
  },
};

export default function App(): JSX.Element {
  return (
    <AgentUI
      config={configText}
      dispatcher={dispatcher}
      agent={agent}
      diagnostics="overlay"
    />
  );
}
