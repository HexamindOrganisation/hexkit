import type { AgentMetadata } from "./types.js";

/**
 * REST helpers for the runtime's non-streaming endpoints. Streaming lives
 * in `sseStream.ts`. Everything goes through Vite's `/api` proxy so the
 * runtime stays CORS-naive.
 */

export async function listAgents(): Promise<AgentMetadata[]> {
  const res = await fetch("/api/agents");
  if (!res.ok) {
    throw new Error(`GET /agents failed: ${res.status}`);
  }
  return res.json();
}

export async function getMetadata(agentId: string): Promise<AgentMetadata> {
  const res = await fetch(
    `/api/agents/${encodeURIComponent(agentId)}/metadata`,
  );
  if (!res.ok) {
    // 404 is significant for the caller (agent doesn't exist) — bake the
    // status into the message so a single `.catch` can branch on it.
    throw new Error(`GET /metadata failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Fetch the per-agent UI definition (raw YAML text).
 *
 * Returns `null` on 404 — the agent didn't ship a `ui.yaml`, so the
 * caller should use its default page config. Any other non-OK status
 * throws.
 *
 * No client-side YAML parsing: `agent-ui` accepts the raw string and
 * parses it itself, with its own diagnostics surface. Less coupling.
 */
export async function getUiYaml(agentId: string): Promise<string | null> {
  const res = await fetch(
    `/api/agents/${encodeURIComponent(agentId)}/ui`,
  );
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`GET /ui failed: ${res.status}`);
  }
  return res.text();
}

export async function cancelRun(
  agentId: string,
  runId: string,
): Promise<boolean> {
  const res = await fetch(
    `/api/agents/${encodeURIComponent(agentId)}/runs/${encodeURIComponent(runId)}/cancel`,
    { method: "POST" },
  );
  if (!res.ok) {
    throw new Error(`cancel failed: ${res.status}`);
  }
  const data = (await res.json()) as { cancelled: boolean };
  return data.cancelled;
}
