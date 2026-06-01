import type { AgentBridge, AgentEvent, ToolCallPayload } from "agent-ui";

import {
  cancelConversation,
  createConversation,
  invokeConversationAction,
} from "../api/conversations";

import { streamChat } from "./sseStream";
import type { RuntimeEvent } from "./types";


/**
 * Widget name that receives tool-call routing payloads. Agents that want a
 * dedicated tool log include a widget by exactly this name in their
 * `ui.yaml`. The default chat config does NOT include this widget — agents
 * stay quiet about tool events unless their YAML opts in.
 */
const TOOL_CALLS_WIDGET = "tool-calls";


export interface BridgeHooks {
  /** Current conversation id, or `null` on the landing page. */
  getConversationId: () => string | null;
  /** Current agent id (URL search param on `/`, conversation row on `/c/:id`). */
  getAgentId: () => string | null;
  /** Called after a lazy `POST /conversations` resolves. The host navigates
   *  to `/c/<id>` and invalidates the conversations query. */
  onConversationCreated: (id: string) => void;
  /** Pre-flight guard. Return an error string to block the submit (used by
   *  the onboarding gate when no keys are set). Return `null` to allow. */
  canSubmit?: () => string | null;
}


/**
 * `AgentBridge` over the platform backend.
 *
 * Lazy conversation creation
 * --------------------------
 * On `/`, the conversation doesn't exist yet. The first `onUserSubmit`
 * POSTs `/conversations` to create one, then calls `onConversationCreated`
 * (the host navigates to `/c/:id` and invalidates the sidebar's
 * conversations query), then opens the chat stream.
 *
 * Event translation
 * -----------------
 *   runtime (event_type)        →   agent-ui (kind)
 *   ───────────────────────         ────────────────
 *   run_start                   →   status: thinking  (already emitted before submit)
 *   block_start  (text)         →   open partial keyed by block_id
 *   block_delta  (text)         →   token
 *   block_end    (text)         →   message (assistant, accumulated)
 *   tool_start                  →   tool-call (TOOL_CALLS_WIDGET, phase: start)
 *   tool_end                    →   tool-call (TOOL_CALLS_WIDGET, phase: end)
 *   run_end                     →   status: idle  (in finally)
 *   error  (details.cancelled)  →   message (system, "Run cancelled.")
 *   error  (everything else)    →   error
 *
 * `reasoning` / `tool_call` block subtypes, `tool_update`, `state_update`,
 * `trace_span`, and the approval_* family are ignored for v0 — their
 * receiving widgets don't exist yet.
 */
export class RuntimeBridge implements AgentBridge {
  private listeners = new Set<(event: AgentEvent) => void>();
  private currentAbort: AbortController | null = null;
  private streaming = false;
  // Accumulated text per active text-block, keyed by block_id.
  private partials = new Map<string, string>();
  // Suppresses a duplicate "Run cancelled." when both the local cancel path
  // and the runtime's cancelled error event would emit one.
  private localCancelEmitted = false;

  constructor(private readonly hooks: BridgeHooks) {}

  subscribeAgentOutput = (cb: (event: AgentEvent) => void): (() => void) => {
    this.listeners.add(cb);
    return () => {
      this.listeners.delete(cb);
    };
  };

  onUserSubmit = async (text: string): Promise<void> => {
    if (this.streaming) {
      // Already streaming. The user has to cancel before starting another run.
      return;
    }

    const guard = this.hooks.canSubmit?.();
    if (guard) {
      this.emit({ kind: "error", message: guard });
      return;
    }

    // Lazy-create the conversation if we're on the landing page.
    let conversationId = this.hooks.getConversationId();
    if (!conversationId) {
      const agentId = this.hooks.getAgentId();
      if (!agentId) {
        this.emit({
          kind: "error",
          message: "Pick an agent from the dropdown before sending.",
        });
        return;
      }
      try {
        const conv = await createConversation({ agent_id: agentId });
        conversationId = conv.id;
        this.hooks.onConversationCreated(conv.id);
      } catch (e) {
        this.emit({
          kind: "error",
          message:
            e instanceof Error ? e.message : "Could not start a new conversation.",
        });
        return;
      }
    }

    this.streaming = true;
    const controller = new AbortController();
    this.currentAbort = controller;
    this.emit({ kind: "status", state: "thinking" });

    try {
      for await (const event of streamChat(
        conversationId,
        text,
        controller.signal,
      )) {
        this.translate(event);
      }
    } catch (e) {
      const isAbort = e instanceof DOMException && e.name === "AbortError";
      if (!isAbort) {
        const message = e instanceof Error ? e.message : String(e);
        this.emit({ kind: "error", message });
      }
    } finally {
      this.flushPartials();
      this.emit({ kind: "status", state: "idle" });
      this.streaming = false;
      this.currentAbort = null;
      this.localCancelEmitted = false;
    }
  };

  cancel = async (): Promise<boolean> => {
    if (!this.streaming) return false;
    const conversationId = this.hooks.getConversationId();

    // Local-first: tear the stream down, finalize partials, surface the
    // marker, then ask the runtime to stop. Means the UI snaps to "cancelled"
    // even if the cancel POST is slow or the network blips.
    this.currentAbort?.abort();
    this.flushPartials();
    this.localCancelEmitted = true;
    this.emit({ kind: "message", role: "system", content: "Run cancelled." });

    if (conversationId) {
      try {
        await cancelConversation(conversationId);
      } catch {
        /* local abort already freed the UI */
      }
    }
    return true;
  };

  invokeAction = async (name: string, args: unknown): Promise<unknown> => {
    const conversationId = this.hooks.getConversationId();
    if (!conversationId) {
      throw new Error("Actions require an active conversation.");
    }
    const { result, events } = await invokeConversationAction(
      conversationId,
      name,
      args,
    );
    for (const event of events) {
      this.emit({
        kind: "tool-call",
        widget: event.widget,
        payload: event.payload,
      });
    }
    return result;
  };

  // ---- internal ------------------------------------------------------------

  private flushPartials(): void {
    for (const [blockId, content] of this.partials) {
      if (!content) continue;
      this.emit({
        kind: "message",
        role: "assistant",
        content,
        messageId: blockId,
      });
    }
    this.partials.clear();
  }

  private translate(event: RuntimeEvent): void {
    switch (event.event_type) {
      case "run_start":
        return;

      case "block_start":
        if (event.block_type === "text") {
          this.partials.set(event.block_id, "");
        }
        return;

      case "block_delta": {
        if (event.block_type !== "text") return;
        const prev = this.partials.get(event.block_id) ?? "";
        this.partials.set(event.block_id, prev + event.text);
        this.emit({
          kind: "token",
          text: event.text,
          messageId: event.block_id,
        });
        return;
      }

      case "block_end": {
        if (event.block_type !== "text") return;
        const content = this.partials.get(event.block_id) ?? "";
        this.partials.delete(event.block_id);
        if (content) {
          this.emit({
            kind: "message",
            role: "assistant",
            content,
            messageId: event.block_id,
          });
        }
        return;
      }

      case "tool_start": {
        const payload: ToolCallPayload = {
          phase: "start",
          id: event.tool_id,
          name: event.tool_name,
          arguments: event.arguments,
        };
        this.emit({
          kind: "tool-call",
          widget: TOOL_CALLS_WIDGET,
          payload,
        });
        return;
      }

      case "tool_end": {
        const errorText =
          event.state === "failed"
            ? event.output_summary ?? "tool failed"
            : null;
        const payload: ToolCallPayload = {
          phase: "end",
          id: event.tool_id,
          name: event.tool_name,
          output: event.output,
          error: errorText,
        };
        this.emit({
          kind: "tool-call",
          widget: TOOL_CALLS_WIDGET,
          payload,
        });
        return;
      }

      case "error":
        // Finalize partials before the terminal marker so the agent's last
        // words land above the cancel/error notice.
        this.flushPartials();
        if (event.details && event.details.cancelled === true) {
          if (this.localCancelEmitted) return;
          this.emit({
            kind: "message",
            role: "system",
            content: "Run cancelled.",
          });
        } else {
          this.emit({ kind: "error", message: event.message });
        }
        return;

      case "run_end":
      case "tool_update":
      case "state_update":
      case "trace_span":
      case "approval_requested":
      case "approval_resolved":
        return;
    }
  }

  private emit(event: AgentEvent): void {
    for (const cb of this.listeners) cb(event);
  }
}
