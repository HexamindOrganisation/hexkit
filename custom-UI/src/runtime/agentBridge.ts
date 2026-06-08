export type AgentEvent =
  | { kind: "token"; text: string; messageId?: string }
  | {
      kind: "message";
      role: "assistant" | "system";
      content: string;
      messageId?: string;
    }
  | { kind: "status"; state: "idle" | "thinking" | "responding" }
  | { kind: "tool-call"; widget?: string; payload: unknown }
  | { kind: "error"; message: string };

/** A file in the user's library / attached to the conversation. */
export interface AgentFile {
  id: string;
  name: string;
  mime: string;
  size: number;
}

/**
 * Optional host-provided file capability. When a bridge exposes `files`, the
 * composer shows an attach affordance. Attachments persist on the conversation
 * (the host forwards them to the backend every turn).
 */
export interface FileService {
  /** All files in the user's global library (for the reuse picker). */
  listLibrary: () => Promise<AgentFile[]>;
  /** Upload new files to the library. Returns the created entries. */
  upload: (files: File[]) => Promise<AgentFile[]>;
  /** Files currently attached to the active conversation. */
  listAttached: () => Promise<AgentFile[]>;
  /** Attach library files to the active conversation; returns the new set. */
  attach: (fileIds: string[]) => Promise<AgentFile[]>;
  /** Detach a file from the active conversation. */
  detach: (fileId: string) => Promise<void>;
}

/**
 * Optional host-provided "context" capability. When a bridge exposes `context`,
 * display widgets (table / markdown) show a toggle that adds their content to
 * the conversation's model context as labeled text (forwarded like a file).
 * Conversation-scoped + persistent across turns; keyed by the widget's name.
 */
export interface ContextService {
  /** Widget keys currently toggled into the conversation's context. */
  list: () => Promise<string[]>;
  /** Upsert a widget's content into context (toggle on / live re-sync). */
  set: (
    key: string,
    item: { label: string; mime: string; text: string },
  ) => Promise<void>;
  /** Remove a widget's content from context (toggle off). */
  remove: (key: string) => Promise<void>;
}

export interface AgentBridge {
  /** Submit a user turn. `options.fileIds` attaches files on the first turn
   *  (before a conversation exists); afterwards the composer attaches directly
   *  via `files`. */
  onUserSubmit: (
    text: string,
    options?: { fileIds?: string[] },
  ) => void | Promise<void>;
  subscribeAgentOutput: (cb: (event: AgentEvent) => void) => () => void;
  /** Cancel the in-flight run: abort the stream and tell the backend to stop.
   *  When absent, the composer falls back to dispatching a `cancel-run` action. */
  cancel?: () => void | Promise<unknown>;
  /** Optional file attachments capability. */
  files?: FileService;
  /** Optional widget-content → context capability (the context toggle). */
  context?: ContextService;
}
