import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Files,
  FolderPlus,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Settings,
} from "lucide-react";

import { useActiveAgent, useFolders } from "../hooks/useActiveAgent";
import { createFolder } from "../api/folders";
import { updateConversation, type Conversation } from "../api/conversations";
import {
  ConversationListItem,
  dragHasConversation,
  readDraggedConversationId,
} from "../components/ConversationListItem";
import { FolderListItem } from "../components/FolderListItem";

/**
 * The constant left chrome:
 *  - brand + New session + New folder
 *  - shared conversation history (ALL agents) grouped by folder + a root list,
 *    each conversation prefixed with its agent's colored glyph
 *  - rename / move-to-folder / delete per row; folder create / rename / delete
 *  - user footer + settings
 */
export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const { agents, agentId, conversationId, conversations } = useActiveAgent();
  const { data: folders = [] } = useFolders();

  const [openFolders, setOpenFolders] = useState<Set<string>>(new Set());
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [folderDraft, setFolderDraft] = useState("");

  const colorFor = (id: string) =>
    agents.find((a) => a.id === id)?.main_color ?? "#6e7177";

  // Group conversations by folder; the rest go to the root list (folder_id null).
  const { byFolder, rootConvos } = useMemo(() => {
    const map = new Map<string, Conversation[]>();
    const root: Conversation[] = [];
    for (const c of conversations) {
      if (c.folder_id) {
        const arr = map.get(c.folder_id) ?? [];
        arr.push(c);
        map.set(c.folder_id, arr);
      } else {
        root.push(c);
      }
    }
    return { byFolder: map, rootConvos: root };
  }, [conversations]);

  const createFolderMut = useMutation({
    mutationFn: (name: string) => createFolder(name),
    onSuccess: (f) => {
      qc.invalidateQueries({ queryKey: ["folders"] });
      setOpenFolders((s) => new Set(s).add(f.id)); // open the new folder
    },
  });

  // Drag-and-drop move (folderId === null → out to root).
  const [rootDragOver, setRootDragOver] = useState(false);
  const moveMut = useMutation({
    mutationFn: ({ convId, folderId }: { convId: string; folderId: string | null }) =>
      updateConversation(
        convId,
        folderId === null ? { clear_folder: true } : { folder_id: folderId },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conversations"] }),
  });

  const dropIntoFolder = (folderId: string, convId: string) => {
    moveMut.mutate({ convId, folderId });
    setOpenFolders((s) => new Set(s).add(folderId));
  };

  function commitNewFolder() {
    const name = folderDraft.trim();
    if (name) createFolderMut.mutate(name);
    setFolderDraft("");
    setCreatingFolder(false);
  }

  const toggleFolder = (id: string) =>
    setOpenFolders((s) => {
      const next = new Set(s);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  return (
    <aside
      className="flex h-full flex-col border-r border-border"
      style={{
        width: collapsed ? 56 : 264,
        background: "var(--hx-bg-2, hsl(var(--background)))",
        transition: "width 0.18s ease",
      }}
    >
      {/* Brand + collapse */}
      <div className="flex items-center justify-between px-3 py-3">
        {!collapsed && (
          <span className="select-none px-1 text-[15px] tracking-tight">
            Hexa<span className="font-bold">UI</span>
          </span>
        )}
        <button
          type="button"
          onClick={onToggle}
          className="hx-srow rounded-md p-1.5 text-muted-foreground hover:bg-secondary"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* New session + New folder */}
      <div className="flex gap-2 px-2">
        <button
          type="button"
          onClick={() => navigate(`/?agent=${agentId ?? ""}&n=${Date.now()}`)}
          className="hx-srow flex flex-1 items-center gap-2 rounded-md border border-border px-2.5 py-2 text-sm hover:bg-secondary"
        >
          <Plus className="h-4 w-4 shrink-0" />
          {!collapsed && <span>New session</span>}
        </button>
        {!collapsed && (
          <button
            type="button"
            onClick={() => {
              setCreatingFolder(true);
              setFolderDraft("");
            }}
            className="hx-srow rounded-md border border-border px-2.5 py-2 text-muted-foreground hover:bg-secondary hover:text-foreground"
            aria-label="New folder"
            title="New folder"
          >
            <FolderPlus className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Files library */}
      <div className="mt-2 px-2">
        <button
          type="button"
          onClick={() => navigate("/files")}
          className={[
            "hx-srow flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm",
            location.pathname === "/files"
              ? "bg-secondary text-foreground"
              : "text-muted-foreground hover:bg-secondary hover:text-foreground",
          ].join(" ")}
          aria-label="Files"
          title="Files"
        >
          <Files className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Files</span>}
        </button>
      </div>

      {/* Shared conversation history */}
      <nav className="mt-3 min-h-0 flex-1 overflow-y-auto px-2">
        {!collapsed && (
          <div className="px-1 pb-1 font-mono text-[11px] uppercase tracking-[0.05em] text-[var(--hx-text-3,hsl(var(--muted-foreground)))]">
            History
          </div>
        )}

        {/* New-folder inline composer */}
        {creatingFolder && !collapsed && (
          <input
            autoFocus
            value={folderDraft}
            placeholder="Folder name…"
            onChange={(e) => setFolderDraft(e.target.value)}
            onBlur={commitNewFolder}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitNewFolder();
              if (e.key === "Escape") {
                setFolderDraft("");
                setCreatingFolder(false);
              }
            }}
            className="hx-appear mb-1 w-full rounded-md border border-[var(--accent-color,hsl(var(--primary)))] bg-background px-2 py-1.5 text-[13px] outline-none placeholder:text-muted-foreground"
          />
        )}

        {/* Folders */}
        {!collapsed &&
          folders.map((f) => {
            const convos = byFolder.get(f.id) ?? [];
            return (
              <div key={f.id} className="hx-appear">
                <FolderListItem
                  folder={f}
                  open={openFolders.has(f.id)}
                  count={convos.length}
                  onToggle={() => toggleFolder(f.id)}
                  onDropConversation={(convId) => dropIntoFolder(f.id, convId)}
                >
                  {convos.length === 0 ? (
                    <div className="px-2 py-1 text-[12px] italic text-muted-foreground">
                      Empty
                    </div>
                  ) : (
                    convos.map((c) => (
                      <ConversationListItem
                        key={c.id}
                        conv={c}
                        folders={folders}
                        color={colorFor(c.agent_id)}
                        active={c.id === conversationId}
                      />
                    ))
                  )}
                </FolderListItem>
              </div>
            );
          })}

        {/* Root conversations — also a drop target (drag here to leave a folder) */}
        <div
          className={[
            "mt-0.5 space-y-0.5 rounded-md transition-shadow",
            rootDragOver && !collapsed
              ? "ring-2 ring-inset ring-[var(--accent-color,hsl(var(--primary)))] bg-secondary/40"
              : "",
          ].join(" ")}
          onDragOver={(e) => {
            if (collapsed || !dragHasConversation(e)) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            if (!rootDragOver) setRootDragOver(true);
          }}
          onDragLeave={(e) => {
            if (e.currentTarget.contains(e.relatedTarget as Node)) return;
            setRootDragOver(false);
          }}
          onDrop={(e) => {
            if (!dragHasConversation(e)) return;
            e.preventDefault();
            setRootDragOver(false);
            const id = readDraggedConversationId(e);
            if (id) moveMut.mutate({ convId: id, folderId: null });
          }}
        >
          {(collapsed ? conversations : rootConvos).map((c) => (
            <ConversationListItem
              key={c.id}
              conv={c}
              folders={folders}
              color={colorFor(c.agent_id)}
              active={c.id === conversationId}
            />
          ))}
          {!collapsed && rootConvos.length === 0 && rootDragOver && (
            <div className="px-2 py-3 text-center text-[12px] italic text-muted-foreground">
              Drop here to remove from folder
            </div>
          )}
        </div>
      </nav>

      {/* User footer + settings */}
      <div className="flex items-center gap-2 border-t border-border px-3 py-3">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-secondary text-xs font-semibold">
          D
        </span>
        {!collapsed && (
          <span className="flex-1 truncate text-sm text-muted-foreground">
            dev01
          </span>
        )}
        <button
          type="button"
          onClick={() => navigate("/settings")}
          className="hx-srow rounded-md p-1.5 text-muted-foreground hover:bg-secondary"
          aria-label="Settings"
          title="Settings"
        >
          <Settings className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
}
