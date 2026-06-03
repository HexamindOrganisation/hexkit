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

export interface AgentBridge {
  /** Submit a user turn. `options.fileIds` attaches files on the first turn
   *  (before a conversation exists); afterwards the composer attaches directly
   *  via `files`. */
  onUserSubmit: (
    text: string,
    options?: { fileIds?: string[] },
  ) => void | Promise<void>;
  subscribeAgentOutput: (cb: (event: AgentEvent) => void) => () => void;
  /** Optional file attachments capability. */
  files?: FileService;
}
