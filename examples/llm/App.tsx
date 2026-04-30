import { AgentUI, type ActionDispatcher, type AgentBridge } from "../../src";
import type { FileTreeNode } from "../../src/schema/widgets/file-tree";
import type { AgentEvent } from "../../src/runtime/agentBridge";
import "../../src/styles.css";
import "../../src/shadcn.css";
import configText from "./config.yaml?raw";

const API = "http://localhost:8000";

const fileTree: FileTreeNode[] = [
  {
    id: "root",
    name: "workspace",
    type: "folder",
    children: [
      {
        id: "docs",
        name: "Documents",
        type: "folder",
        children: [
          { id: "docs/report", name: "report.pdf", type: "file", size: 245_000 },
          { id: "docs/notes", name: "notes.md", type: "file", size: 12_400 },
        ],
      },
      { id: "invoice", name: "invoice.xlsx", type: "file", size: 88_200 },
      { id: "readme", name: "README.md", type: "file", size: 3_200 },
    ],
  },
];

let currentConversationId: string | null = null;
const conversationLog: { role: "user" | "assistant"; content: string }[] = [];

// Subscribers interested in the conversation list. Notified whenever we
// create a new conversation so the history widget refreshes immediately.
const conversationListSubs = new Set<(d: unknown) => void>();

async function fetchConversations(): Promise<unknown> {
  const res = await fetch(`${API}/conversations`);
  if (!res.ok) throw new Error(`list_conversations: ${res.status}`);
  return res.json();
}

async function notifyConversationListChanged(): Promise<void> {
  if (conversationListSubs.size === 0) return;
  try {
    const data = await fetchConversations();
    conversationListSubs.forEach((cb) => cb(data));
  } catch {
    // best-effort; widgets keep their last good data
  }
}

async function createConversation(): Promise<{ id: string }> {
  const res = await fetch(`${API}/conversations`, { method: "POST" });
  if (!res.ok) throw new Error(`create_conversation: ${res.status}`);
  const summary = await res.json();
  currentConversationId = summary.id;
  conversationLog.length = 0;
  await notifyConversationListChanged();
  return summary;
}

const dispatcher: ActionDispatcher = {
  async invoke(action, args) {
    switch (action) {
      case "list_user_files":
        return fileTree;
      case "open_file": {
        const file = (args as { file: { name: string } }).file;
        alert(`Open ${file.name}`);
        return;
      }
      case "delete_file":
        return;
      case "refresh_data":
      case "open_settings":
      case "delete_all":
        alert(action);
        return;
      case "list_conversations":
        return fetchConversations();
      case "load_conversation": {
        const { id } = args as { id: string };
        const res = await fetch(`${API}/conversations/${encodeURIComponent(id)}`);
        if (!res.ok) throw new Error(`load_conversation: ${res.status}`);
        const messages = (await res.json()) as {
          id: string;
          role: "user" | "assistant" | "system";
          content: string;
        }[];
        currentConversationId = id;
        conversationLog.length = 0;
        for (const m of messages) {
          if (m.role === "user" || m.role === "assistant") {
            conversationLog.push({ role: m.role, content: m.content });
          }
        }
        return messages.map((m) => ({ ...m, timestamp: Date.now() }));
      }
      case "create_conversation":
        return createConversation();
      default:
        return;
    }
  },
  subscribe(action, _args, onData, onError) {
    if (action !== "list_conversations") {
      return () => {};
    }
    conversationListSubs.add(onData);
    fetchConversations()
      .then((d) => onData(d))
      .catch((e) => onError?.(e));
    return () => {
      conversationListSubs.delete(onData);
    };
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
      // Title/preview were updated server-side after the first user message.
      await notifyConversationListChanged();
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
