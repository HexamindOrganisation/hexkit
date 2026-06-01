import { authedFetch, getJson } from "./client";

export interface AgentCapabilities {
  streaming: boolean;
  tools: boolean;
  state: boolean;
  approvals: boolean;
  multi_turn: boolean;
}

export interface AgentMetadata {
  agent_id: string;
  name: string;
  framework: string;
  version: string;
  description: string;
  capabilities: AgentCapabilities;
  actions: string[];
  extra: Record<string, unknown>;
}

export function listAgents(): Promise<AgentMetadata[]> {
  return getJson<AgentMetadata[]>("/api/agents");
}

export function getAgentMetadata(agentId: string): Promise<AgentMetadata> {
  return getJson<AgentMetadata>(`/api/agents/${agentId}/metadata`);
}

/**
 * Returns the agent's YAML body, or `null` if the agent ships no `ui.yaml`
 * (the front-app falls back to its bundled default chat config).
 */
export async function getAgentUiYaml(agentId: string): Promise<string | null> {
  const resp = await authedFetch(`/api/agents/${agentId}/ui`);
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`Failed to fetch ui.yaml: HTTP ${resp.status}`);
  return await resp.text();
}
