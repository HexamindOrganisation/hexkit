import { del, getJson, postJson } from "./client";

/** A file in the user's global library. */
export interface FileMeta {
  id: string;
  name: string;
  mime: string;
  size: number;
  created_at: string;
}

// ---- Library (global, user-scoped) ----------------------------------------

export function listFiles(): Promise<FileMeta[]> {
  return getJson<FileMeta[]>("/api/files");
}

export async function uploadFile(file: File): Promise<FileMeta> {
  const form = new FormData();
  form.append("file", file);
  // Plain fetch (not authedFetch): we must NOT set Content-Type so the browser
  // adds the multipart boundary. Single-user proxy needs no auth header.
  const resp = await fetch("/api/files", { method: "POST", body: form });
  if (!resp.ok) throw new Error(`Upload failed: HTTP ${resp.status}`);
  return (await resp.json()) as FileMeta;
}

export function deleteFile(id: string): Promise<void> {
  return del(`/api/files/${id}`);
}

/** URL to fetch/preview a file's content (served with its mime). */
export function fileContentUrl(id: string): string {
  return `/api/files/${id}`;
}

// ---- Conversation attachments (persist across turns) ----------------------

export function listConversationFiles(convId: string): Promise<FileMeta[]> {
  return getJson<FileMeta[]>(`/api/conversations/${convId}/files`);
}

export function attachFiles(
  convId: string,
  fileIds: string[],
): Promise<FileMeta[]> {
  return postJson<FileMeta[]>(`/api/conversations/${convId}/files`, {
    file_ids: fileIds,
  });
}

export function detachConversationFile(
  convId: string,
  fileId: string,
): Promise<void> {
  return del(`/api/conversations/${convId}/files/${fileId}`);
}
