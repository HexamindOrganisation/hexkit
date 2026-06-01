import { authedFetch, getJson } from "./client";

/**
 * Roster entry from the proxy's `GET /agents` (HexaUI contract). `main_color`
 * is the agent's signature hue — the one color that recolors the page.
 */
export interface AgentSummary {
  id: string;
  name: string;
  role: string;
  main_color: string;
  ui_url: string;
}

export function listAgents(): Promise<AgentSummary[]> {
  return getJson<AgentSummary[]>("/api/agents");
}

/**
 * Returns the agent's `ui.yaml` body, or `null` if the agent ships none
 * (the shell falls back to a default chat layout).
 */
export async function getAgentUiYaml(agentId: string): Promise<string | null> {
  const resp = await authedFetch(`/api/agents/${agentId}/ui`);
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`Failed to fetch ui.yaml: HTTP ${resp.status}`);
  return await resp.text();
}
