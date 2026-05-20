import type {
  AgentBridge,
  AgentEvent,
  ToolCallPayload,
} from "agent-ui";
import { cancelRun } from "./api.js";
import { streamRun } from "./sseStream.js";
import type { RuntimeEvent } from "./types.js";

/**
 * Name of the widget that receives tool-call routing payloads. Agents
 * that want a dedicated tool log include a widget by exactly this name
 * in their `ui.yaml`. When no such widget exists, the lib drops the
 * event with a console diagnostic — the chat transcript stays clean of
 * tool noise either way.
 */
const TOOL_CALLS_WIDGET = "tool-calls";

/**
 * Implements `agent-ui`'s `AgentBridge` interface against the platform
 * runtime's HTTP+SSE API.
 *
 * Event translation
 * -----------------
 * The runtime emits a richer, closed-set event vocabulary
 * (message.delta, tool.start, state.update, trace.span, …).
 * `agent-ui` consumes a smaller set (token, message, status, tool-call,
 * error). This bridge is the translation seam — every runtime event
 * becomes zero or one `AgentEvent`.
 *
 *   runtime                    agent-ui
 *   ─────────────────          ─────────────────
 *   run.started        →       status: thinking
 *   message.delta      →       token
 *   message.completed  →       message (assistant)
 *   tool.start         →       tool-call (routed to TOOL_CALLS_WIDGET)
 *   tool.end           →       tool-call (routed to TOOL_CALLS_WIDGET)
 *   error              →       error (or system "Run cancelled" if details.cancelled)
 *   run.completed      →       status: idle
 *
 * Tool routing
 * ------------
 * Tool events used to render as `[tool] foo(args)` system messages in the
 * chat transcript. That mixed tool noise with user/assistant text. Now
 * they emit as `tool-call` payloads aimed at a widget named `tool-calls`
 * (see TOOL_CALLS_WIDGET). Agents that include such a widget in their
 * `ui.yaml` get a dedicated tool log; agents that don't see no chat
 * pollution and a single console diagnostic from the lib.
 *
 * Cancellation
 * ------------
 * Holds the current run's id + an AbortController. `cancel()` calls the
 * runtime's POST /runs/{run_id}/cancel and also aborts the fetch — the
 * latter is a fallback for the case where the runtime has already
 * disconnected.
 */
export class RuntimeBridge implements AgentBridge {
  private listeners = new Set<(event: AgentEvent) => void>();
  private currentRunId: string | null = null;
  private currentAbort: AbortController | null = null;
  // Accumulated text per in-flight message_id. Used to finalize orphan
  // partials when a run ends without a matching `message.completed`.
  private inFlightPartials = new Map<string, string>();
  // Prevents duplicate "Run cancelled." when both cancel() and the
  // runtime's cancelled error event would emit it.
  private localCancelEmitted = false;

  constructor(
    private readonly agentId: string,
    private readonly framework: string,
  ) {}

  subscribeAgentOutput = (cb: (event: AgentEvent) => void): (() => void) => {
    this.listeners.add(cb);
    return () => {
      this.listeners.delete(cb);
    };
  };

  onUserSubmit = async (text: string): Promise<void> => {
    if (this.currentRunId) {
      // Already streaming. Ignore the second submit; the UI cancel button
      // is the right way to stop the current run before a new one.
      return;
    }

    const runId = crypto.randomUUID();
    const controller = new AbortController();
    this.currentRunId = runId;
    this.currentAbort = controller;

    this.emit({ kind: "status", state: "thinking" });

    try {
      const body = {
        input: this.buildInput(text),
        run_id: runId,
      };

      for await (const event of streamRun(this.agentId, body, controller.signal)) {
        this.translate(event);
      }
    } catch (e: unknown) {
      const isAbort = e instanceof DOMException && e.name === "AbortError";
      if (!isAbort) {
        const message = e instanceof Error ? e.message : String(e);
        this.emit({ kind: "error", message });
      }
    } finally {
      this.flushPartials();
      this.emit({ kind: "status", state: "idle" });
      this.currentRunId = null;
      this.currentAbort = null;
      this.localCancelEmitted = false;
    }
  };

  cancel = async (): Promise<boolean> => {
    const runId = this.currentRunId;
    if (!runId) return false;

    // Local-first so the UI reacts instantly and can't race with late
    // runtime events: abort the stream, finalize any partial bubble,
    // emit the cancel marker, then tell the runtime to stop.
    this.currentAbort?.abort();
    this.flushPartials();
    this.localCancelEmitted = true;
    this.emit({
      kind: "message",
      role: "system",
      content: "Run cancelled.",
    });

    try {
      await cancelRun(this.agentId, runId);
    } catch {
      // The local abort already freed the UI; swallow.
    }
    return true;
  };

  private flushPartials(): void {
    for (const [messageId, content] of this.inFlightPartials) {
      if (!content) continue;
      this.emit({
        kind: "message",
        role: "assistant",
        content,
        messageId,
      });
    }
    this.inFlightPartials.clear();
  }

  // ---- internal ----------------------------------------------------------

  private buildInput(text: string): unknown {
    // The HTTP `input` field is adapter-specific by design. LangChain-family
    // agents expect a chat-history shape; OpenAI Agents and Google ADK take
    // a raw string. We branch on the manifest's framework value (already
    // fetched at App startup).
    switch (this.framework) {
      case "langchain":
      case "langgraph":
      case "deepagents":
        return { messages: [{ role: "user", content: text }] };
      default:
        return text;
    }
  }

  private translate(event: RuntimeEvent): void {
    switch (event.type) {
      case "run.started":
        // status already emitted in onUserSubmit; nothing more to surface.
        return;

      case "message.delta": {
        const prev = this.inFlightPartials.get(event.message_id) ?? "";
        this.inFlightPartials.set(event.message_id, prev + event.delta);
        this.emit({
          kind: "token",
          text: event.delta,
          messageId: event.message_id,
        });
        return;
      }

      case "message.completed":
        this.inFlightPartials.delete(event.message_id);
        this.emit({
          kind: "message",
          role: event.role === "assistant" ? "assistant" : "system",
          content: event.content,
          messageId: event.message_id,
        });
        return;

      case "tool.start": {
        const payload: ToolCallPayload = {
          phase: "start",
          id: event.tool_call_id,
          name: event.name,
          arguments: event.arguments,
        };
        this.emit({
          kind: "tool-call",
          widget: TOOL_CALLS_WIDGET,
          payload,
        });
        return;
      }

      case "tool.end": {
        const payload: ToolCallPayload = {
          phase: "end",
          id: event.tool_call_id,
          name: event.name,
          output: event.output,
          error: event.error,
        };
        this.emit({
          kind: "tool-call",
          widget: TOOL_CALLS_WIDGET,
          payload,
        });
        return;
      }

      case "state.update":
        // Useful but noisy in chat; render only multi-agent handoffs.
        if (event.key === "active_agent") {
          this.emit({
            kind: "message",
            role: "system",
            content: `[active agent] ${String(event.value)}`,
          });
        }
        return;

      case "error":
        // Finalize any partial before the terminal marker so it doesn't
        // render above the agent's last words.
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

      case "run.completed":
        // status: idle is emitted in onUserSubmit's finally.
        return;

      // trace.span / approval.requested: not surfaced in chat for v0.
      default:
        return;
    }
  }

  private emit(event: AgentEvent): void {
    for (const cb of this.listeners) cb(event);
  }
}

