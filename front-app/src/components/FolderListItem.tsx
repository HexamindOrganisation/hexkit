import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Folder as FolderIcon, MoreHorizontal, Pencil, Trash2 } from "lucide-react";

import { deleteFolder, Folder, renameFolder } from "../api/folders";
import { ConfirmDialog } from "./ConfirmDialog";
import { PortalMenu } from "./PortalMenu";
import {
  dragHasConversation,
  readDraggedConversationId,
} from "./ConversationListItem";

/**
 * A collapsible folder in the sidebar. Liquid expand/collapse via grid-rows
 * (`.hx-collapse`), a rotating chevron, inline rename, delete (which moves its
 * conversations back to the root, server-side via FK SET NULL), a portal menu
 * (so it isn't clipped or covered), and a drop target — drag a conversation
 * onto it to move it in.
 */
export function FolderListItem({
  folder,
  open,
  count,
  onToggle,
  onDropConversation,
  children,
}: {
  folder: Folder;
  open: boolean;
  count: number;
  onToggle: () => void;
  onDropConversation: (conversationId: string) => void;
  children: React.ReactNode;
}) {
  const qc = useQueryClient();
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(folder.name);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);

  const renameMut = useMutation({
    mutationFn: (name: string) => renameFolder(folder.id, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["folders"] }),
  });
  const deleteMut = useMutation({
    mutationFn: () => deleteFolder(folder.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["folders"] });
      // Child conversations get folder_id=NULL server-side → root list is stale.
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  function commitRename() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== folder.name) renameMut.mutate(trimmed);
    setRenaming(false);
  }

  return (
    <div>
      <div
        className={[
          "group relative flex items-center gap-1 rounded-md transition-shadow",
          dragOver
            ? "bg-secondary/50 ring-2 ring-inset ring-[var(--accent-color,hsl(var(--primary)))]"
            : "",
        ].join(" ")}
        onDragOver={(e) => {
          if (!dragHasConversation(e)) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          if (!dragOver) setDragOver(true);
        }}
        onDragLeave={(e) => {
          if (e.currentTarget.contains(e.relatedTarget as Node)) return;
          setDragOver(false);
        }}
        onDrop={(e) => {
          if (!dragHasConversation(e)) return;
          e.preventDefault();
          setDragOver(false);
          const id = readDraggedConversationId(e);
          if (id) onDropConversation(id);
        }}
      >
        {renaming ? (
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitRename}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitRename();
              if (e.key === "Escape") {
                setDraft(folder.name);
                setRenaming(false);
              }
            }}
            className="my-0.5 w-full rounded-md border border-[var(--accent-color,hsl(var(--primary)))] bg-background px-2 py-1 text-[13px] outline-none"
          />
        ) : (
          <button
            type="button"
            onClick={onToggle}
            className="hx-srow flex flex-1 items-center gap-1.5 truncate rounded-md px-1.5 py-1.5 text-left hover:bg-secondary/60"
          >
            <ChevronRight
              className="hx-chev h-3.5 w-3.5 shrink-0 text-muted-foreground"
              data-open={open}
            />
            <FolderIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="flex-1 truncate text-[13.5px] text-foreground/90">
              {folder.name}
            </span>
            <span className="shrink-0 font-mono text-[10.5px] text-[var(--hx-text-3,hsl(var(--muted-foreground)))]">
              {count || ""}
            </span>
          </button>
        )}

        {!renaming && (
          <button
            ref={btnRef}
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-expanded={menuOpen}
            className="rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100 aria-expanded:opacity-100"
            aria-label="Folder actions"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
        )}

        <PortalMenu
          open={menuOpen}
          onClose={() => setMenuOpen(false)}
          anchorRef={btnRef}
          width={160}
        >
          <button
            type="button"
            onClick={() => {
              setDraft(folder.name);
              setRenaming(true);
              setMenuOpen(false);
            }}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-secondary"
          >
            <Pencil className="h-3.5 w-3.5" /> Rename
          </button>
          <button
            type="button"
            onClick={() => {
              setConfirmDelete(true);
              setMenuOpen(false);
            }}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-destructive transition-colors hover:bg-secondary"
          >
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </button>
        </PortalMenu>
      </div>

      {/* Liquid expand/collapse — grid-rows 0fr↔1fr, inner overflow hidden. */}
      <div className="hx-collapse" data-open={open}>
        <div>
          <div className="ml-3 space-y-0.5 border-l border-border/60 pb-1 pl-2 pt-0.5">
            {children}
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete folder?"
        body={
          <>
            <span className="font-medium text-foreground">{folder.name}</span>{" "}
            will be removed. Conversations inside it move back to the root list.
          </>
        }
        confirmLabel="Delete"
        destructive
        onConfirm={() => {
          deleteMut.mutate();
          setConfirmDelete(false);
        }}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}
