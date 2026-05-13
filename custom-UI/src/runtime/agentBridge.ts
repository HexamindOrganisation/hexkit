export type AgentEvent =
  | { kind: "token"; text: string; messageId?: string }
  | {
      kind: "message";
      role: "assistant" | "system";
      content: string;
      messageId?: string;
    }
  | { kind: "status"; state: "idle" | "thinking" | "responding" }
  | { kind: "tool-call"; widget: string; payload: unknown }
  | { kind: "error"; message: string };

export interface AgentBridge {
  onUserSubmit: (text: string) => void | Promise<void>;
  subscribeAgentOutput: (cb: (event: AgentEvent) => void) => () => void;
}
