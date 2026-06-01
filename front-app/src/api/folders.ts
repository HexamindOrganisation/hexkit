import { del, getJson, patchJson, postJson } from "./client";

export interface Folder {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export function listFolders(): Promise<Folder[]> {
  return getJson<Folder[]>("/api/folders");
}

export function createFolder(name: string): Promise<Folder> {
  return postJson<Folder>("/api/folders", { name });
}

export function renameFolder(id: string, name: string): Promise<Folder> {
  return patchJson<Folder>(`/api/folders/${id}`, { name });
}

export function deleteFolder(id: string): Promise<void> {
  return del(`/api/folders/${id}`);
}
