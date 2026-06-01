import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { FolderPlus, Plus, Search } from "lucide-react";

import { Conversation, listConversations } from "../api/conversations";
import { createFolder, Folder, listFolders } from "../api/folders";
import { ConversationListItem } from "../components/ConversationListItem";
import { FolderListItem } from "../components/FolderListItem";


/**
 * Left rail: new-chat, search, folders + conversations.
 *
 * Search filter is client-side (substring on title). Server-side FTS is
 * post-v0. Folders + their conversations render under each folder header;
 * conversations with no folder live in a "no folder" group at the top.
 */
export function Sidebar({
  currentAgentId,
  onClose,
}: {
  currentAgentId: string | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const conversations = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
  });
  const folders = useQuery({ queryKey: ["folders"], queryFn: listFolders });

  const [filter, setFilter] = useState("");
  const [collapsedFolders, setCollapsedFolders] = useState<Set<string>>(
    new Set(),
  );

  const folderListData = folders.data ?? [];
  const convListData = conversations.data ?? [];

  const filtered = useMemo(() => {
    if (!filter.trim()) return convListData;
    const q = filter.toLowerCase();
    return convListData.filter((c) => (c.title ?? "").toLowerCase().includes(q));
  }, [convListData, filter]);

  // Group conversations by folder_id. `null` group renders first.
  const groups = useMemo(() => {
    const root: Conversation[] = [];
    const byFolder = new Map<string, Conversation[]>();
    for (const c of filtered) {
      if (c.folder_id) {
        const arr = byFolder.get(c.folder_id) ?? [];
        arr.push(c);
        byFolder.set(c.folder_id, arr);
      } else {
        root.push(c);
      }
    }
    return { root, byFolder };
  }, [filtered]);

  const newFolderMut = useMutation({
    mutationFn: (name: string) => createFolder(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["folders"] }),
  });

  function onNewChat() {
    // "New chat" returns to the landing page with the currently-selected agent
    // baked in as a URL param. Phase F3 creates the conversation lazily on the
    // first submitted message.
    const search = currentAgentId ? `?agent=${encodeURIComponent(currentAgentId)}` : "";
    navigate(`/${search}`);
    onClose();
  }

  function onNewFolder() {
    const name = prompt("Folder name?");
    if (!name) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    newFolderMut.mutate(trimmed);
  }

  function toggleFolder(id: string) {
    setCollapsedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="flex h-full flex-col p-3">
      <div className="flex items-center gap-1">
        <button
          onClick={onNewChat}
          className="flex flex-1 items-center justify-center gap-2 rounded border border-border bg-background px-3 py-1.5 text-sm hover:bg-muted"
        >
          <Plus className="h-3.5 w-3.5" /> New chat
        </button>
        <button
          onClick={onNewFolder}
          title="New folder"
          className="rounded border border-border bg-background p-1.5 hover:bg-muted"
        >
          <FolderPlus className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="mt-3 flex items-center gap-2 rounded border border-border bg-background px-2.5">
        <Search className="h-3.5 w-3.5 text-muted-foreground" />
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search conversations"
          className="w-full bg-transparent py-1.5 text-sm focus:outline-none"
        />
      </div>

      <div className="mt-3 flex-1 overflow-y-auto pr-1">
        {conversations.isLoading || folders.isLoading ? (
          <div className="px-1 py-2 text-xs text-muted-foreground">
            Loading…
          </div>
        ) : (
          <>
            {/* Root group (no folder) */}
            {groups.root.length > 0 && (
              <div className="mb-3 space-y-0.5">
                {groups.root.map((c) => (
                  <ConversationListItem
                    key={c.id}
                    conv={c}
                    folders={folderListData}
                  />
                ))}
              </div>
            )}

            {/* Folder groups, alphabetical. */}
            {[...folderListData]
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((f) => (
                <FolderGroup
                  key={f.id}
                  folder={f}
                  conversations={groups.byFolder.get(f.id) ?? []}
                  folders={folderListData}
                  collapsed={collapsedFolders.has(f.id)}
                  onToggle={() => toggleFolder(f.id)}
                />
              ))}

            {groups.root.length === 0 &&
              folderListData.length === 0 && (
                <div className="px-1 py-2 text-xs text-muted-foreground">
                  No conversations yet. Send a message to create one.
                </div>
              )}
          </>
        )}
      </div>
    </div>
  );
}


function FolderGroup({
  folder,
  conversations,
  folders,
  collapsed,
  onToggle,
}: {
  folder: Folder;
  conversations: Conversation[];
  folders: Folder[];
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <FolderListItem folder={folder} collapsed={collapsed} onToggle={onToggle}>
      {conversations.length === 0 ? (
        <div className="px-2 py-1 text-xs text-muted-foreground">empty</div>
      ) : (
        conversations.map((c) => (
          <ConversationListItem key={c.id} conv={c} folders={folders} />
        ))
      )}
    </FolderListItem>
  );
}
