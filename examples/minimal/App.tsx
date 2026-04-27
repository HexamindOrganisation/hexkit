import { AgentUI, type ActionDispatcher, type AgentBridge } from "../../src";
import type { FileTreeNode } from "../../src/schema/widgets/file-tree";
import type { ConversationSummary } from "../../src/schema/widgets/ai-history";
import type { ConversationMessage } from "../../src";
import "../../src/styles.css";
import "../../src/shadcn.css";
import configText from "./config.yaml?raw";

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

const conversationSummaries: ConversationSummary[] = [
  {
    id: "c1",
    title: "Quarterly report review",
    preview: "Walk me through the Q3 numbers…",
    timestamp: Date.now() - 1000 * 60 * 60 * 24,
  },
  {
    id: "c2",
    title: "Refactor the billing module",
    preview: "Here's the plan for splitting out invoices.",
    timestamp: Date.now() - 1000 * 60 * 60 * 4,
  },
  {
    id: "c3",
    title: "Onboarding doc draft",
    preview: "I drafted the welcome guide…",
    timestamp: Date.now() - 1000 * 60 * 30,
  },
];

const conversationStore: Record<string, ConversationMessage[]> = {
  c1: [
    { id: "c1-1", role: "user",      content: "Walk me through the Q3 numbers.",                                         timestamp: Date.now() - 1000 * 60 * 60 * 24 },
    { id: "c1-2", role: "assistant", content: "Revenue was $4.2M, up 18% YoY. Margins held at 42%. Want me to dig in?", timestamp: Date.now() - 1000 * 60 * 60 * 24 + 5000 },
    { id: "c1-3", role: "user",      content: "Focus on customer acquisition cost.",                                    timestamp: Date.now() - 1000 * 60 * 60 * 24 + 12000 },
    { id: "c1-4", role: "assistant", content: "CAC dropped from $312 to $268 — mostly from the referral program scaling.", timestamp: Date.now() - 1000 * 60 * 60 * 24 + 17000 },
  ],
  c2: [
    { id: "c2-1", role: "user",      content: "Here's the plan for splitting out invoices.",       timestamp: Date.now() - 1000 * 60 * 60 * 4 },
    { id: "c2-2", role: "assistant", content: "Looks good. The migration is the riskiest part — let's stage it.", timestamp: Date.now() - 1000 * 60 * 60 * 4 + 8000 },
  ],
  c3: [
    { id: "c3-1", role: "user",      content: "I drafted the welcome guide.",                       timestamp: Date.now() - 1000 * 60 * 30 },
    { id: "c3-2", role: "assistant", content: "Section 3 is doing the heavy lifting — consider moving it earlier.", timestamp: Date.now() - 1000 * 60 * 30 + 4000 },
  ],
};

const dispatcher: ActionDispatcher = {
  async invoke(action, args) {
    console.log("[action]", action, args);
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
        return conversationSummaries;
      case "load_conversation": {
        const { id } = args as { id: string };
        return conversationStore[id] ?? [];
      }
      default:
        return;
    }
  },
  has() {
    return true;
  },
};

let assistantReplies = 0;
const agent: AgentBridge = {
  async onUserSubmit(text) {
    console.log("[user]", text);
    assistantReplies += 1;
    setTimeout(() => {
      lastEmit?.({
        kind: "message",
        messageId: `reply-${assistantReplies}`,
        role: "assistant",
        content: `(echo) ${text}`,
      });
    }, 400);
  },
  subscribeAgentOutput(cb) {
    lastEmit = cb;
    const h = setTimeout(() => {
      cb({
        kind: "message",
        messageId: "greeting",
        role: "assistant",
        content: "Hello from the agent!",
      });
    }, 500);
    return () => {
      clearTimeout(h);
      lastEmit = null;
    };
  },
};

let lastEmit: ((event: Parameters<Parameters<AgentBridge["subscribeAgentOutput"]>[0]>[0]) => void) | null = null;

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
