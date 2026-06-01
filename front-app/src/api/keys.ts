import { del, getJson, putJson } from "./client";

export type Provider = "openai" | "anthropic" | "google";

export const PROVIDERS: Provider[] = ["openai", "anthropic", "google"];

export interface KeyPresence {
  provider: Provider;
  present: true;
  updated_at: string;
}

export function listKeys(): Promise<KeyPresence[]> {
  return getJson<KeyPresence[]>("/api/me/keys");
}

export function putKey(provider: Provider, value: string): Promise<void> {
  return putJson<void>(`/api/me/keys/${provider}`, { value });
}

export function deleteKey(provider: Provider): Promise<void> {
  return del(`/api/me/keys/${provider}`);
}
