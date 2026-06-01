import { del, getJson, patchJson, postJson } from "./client";

export interface Conversation {
  id: string;
  agent_id: string;
  folder_id: string | null;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessageRow {
  id: string;
  role: "user" | "assistant";
  content: string;
  run_id: string | null;
  created_at: string;
}

export function listConversations(): Promise<Conversation[]> {
  return getJson<Conversation[]>("/api/conversations");
}

export interface CreateConversationBody {
  agent_id: string;
  folder_id?: string | null;
  title?: string | null;
}

export function createConversation(
  body: CreateConversationBody,
): Promise<Conversation> {
  return postJson<Conversation>("/api/conversations", body);
}

export interface UpdateConversationBody {
  title?: string | null;
  folder_id?: string | null;
  clear_folder?: boolean;
}

export function updateConversation(
  id: string,
  body: UpdateConversationBody,
): Promise<Conversation> {
  return patchJson<Conversation>(`/api/conversations/${id}`, body);
}

export function deleteConversation(id: string): Promise<void> {
  return del(`/api/conversations/${id}`);
}

export function listMessages(id: string): Promise<ConversationMessageRow[]> {
  return getJson<ConversationMessageRow[]>(`/api/conversations/${id}/messages`);
}

export interface CancelResult {
  cancelled: boolean;
}

export function cancelConversation(id: string): Promise<CancelResult> {
  return postJson<CancelResult>(`/api/conversations/${id}/cancel`);
}

export interface ActionResult {
  result: unknown;
  events: { widget: string; payload: unknown }[];
}

export function invokeConversationAction(
  id: string,
  name: string,
  args: unknown,
): Promise<ActionResult> {
  return postJson<ActionResult>(`/api/conversations/${id}/actions/${name}`, {
    args,
  });
}
