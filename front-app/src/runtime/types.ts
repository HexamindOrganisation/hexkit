/**
 * TS mirror of the platform-runtime's Fortify-shared event schema.
 *
 * Authoritative source: `backend-runtime/src/platform_runtime/events.py`. Keep
 * this file in sync when the runtime adds variants — adapters fail soft
 * (`runtimeBridge` ignores unknown event_types), but typed handling is the
 * point.
 *
 * Discriminator: `event_type`. The base envelope (`event_id`, `run_id`,
 * `sequence`, `timestamp`, …) is the same on every variant.
 */

// ---------------------------------------------------------------------------
// Base envelope
// ---------------------------------------------------------------------------

export interface BaseStreamEvent {
  event_id: string;
  run_id: string;
  root_run_id: string;
  parent_run_id: string | null;
  depth: number;
  sequence: number;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Block model
// ---------------------------------------------------------------------------

export type BlockType = "text" | "reasoning" | "tool_call";

export type BlockRole = "assistant" | "user" | "system" | "tool";

// ---------------------------------------------------------------------------
// Tool model
// ---------------------------------------------------------------------------

export type ToolCallState = "started" | "completed" | "failed";

// ---------------------------------------------------------------------------
// AgentRunResult (carried by run_end)
// ---------------------------------------------------------------------------

export type Step =
  | { type: "text_step"; text: string; id: string; run_id: string; root_run_id: string; parent_run_id: string | null; depth: number; sequence: number }
  | { type: "reasoning_step"; text: string; id: string; run_id: string; root_run_id: string; parent_run_id: string | null; depth: number; sequence: number }
  | {
      type: "tool_call_step";
      tool_name: string;
      arguments: Record<string, unknown>;
      state: ToolCallState;
      output_summary: string | null;
      raw_output: unknown | null;
      id: string;
      run_id: string;
      root_run_id: string;
      parent_run_id: string | null;
      depth: number;
      sequence: number;
    };

export interface AgentRunResult {
  run_id: string;
  root_run_id: string;
  message: string;
  steps: Step[];
}

// ---------------------------------------------------------------------------
// HITL helpers
// ---------------------------------------------------------------------------

export type ApprovalSource = "policy" | "agent";
export type ApprovalKind = "authorize" | "input";
export type ApprovalDecision = "approved" | "denied";

// ---------------------------------------------------------------------------
// Discriminated union of every event_type
// ---------------------------------------------------------------------------

export type RuntimeEvent =
  // Core (Fortify parity) -----------------------------------------------------
  | (BaseStreamEvent & {
      event_type: "run_start";
      query: string;
      agent_id: string | null;
      input: Record<string, unknown>;
    })
  | (BaseStreamEvent & {
      event_type: "block_start";
      block_id: string;
      block_type: BlockType;
      role: BlockRole;
    })
  | (BaseStreamEvent & {
      event_type: "block_delta";
      block_id: string;
      block_type: BlockType;
      text: string;
      role: BlockRole;
    })
  | (BaseStreamEvent & {
      event_type: "block_end";
      block_id: string;
      block_type: BlockType;
      role: BlockRole;
    })
  | (BaseStreamEvent & {
      event_type: "tool_start";
      tool_id: string;
      tool_name: string;
      arguments: Record<string, unknown>;
    })
  | (BaseStreamEvent & {
      event_type: "tool_update";
      tool_id: string;
      tool_name: string;
      text: string;
    })
  | (BaseStreamEvent & {
      event_type: "tool_end";
      tool_id: string;
      tool_name: string;
      state: ToolCallState;
      output_summary: string | null;
      output: unknown;
    })
  | (BaseStreamEvent & {
      event_type: "run_end";
      result: AgentRunResult;
      output: unknown;
    })
  | (BaseStreamEvent & {
      event_type: "error";
      message: string;
      recoverable: boolean;
      details: Record<string, unknown>;
    })
  // Platform observability (additive) ---------------------------------------
  | (BaseStreamEvent & {
      event_type: "state_update";
      key: string;
      value: unknown;
    })
  | (BaseStreamEvent & {
      event_type: "trace_span";
      span_id: string;
      parent_span_id: string | null;
      name: string;
      start_ts: string;
      end_ts: string | null;
      attributes: Record<string, unknown>;
    })
  // HITL (typed; widgets land post-v0) --------------------------------------
  | (BaseStreamEvent & {
      event_type: "approval_requested";
      approval_id: string;
      source: ApprovalSource;
      kind: ApprovalKind;
      reason: string;
      tool_name: string | null;
      arguments: Record<string, unknown>;
      payload: Record<string, unknown>;
    })
  | (BaseStreamEvent & {
      event_type: "approval_resolved";
      approval_id: string;
      decision: ApprovalDecision;
      decided_by: string | null;
      note: string | null;
    });

// ---------------------------------------------------------------------------
// Misc shapes the FE consumes outside the event stream
// ---------------------------------------------------------------------------

export interface WidgetEvent {
  widget: string;
  payload: unknown;
}

export interface ActionResult {
  result: unknown;
  events: WidgetEvent[];
}
