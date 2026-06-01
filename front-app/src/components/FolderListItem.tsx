import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, MoreHorizontal, Pencil, Trash2 } from "lucide-react";

import { deleteFolder, Folder, renameFolder } from "../api/folders";

import { ConfirmDialog } from "./ConfirmDialog";


export function FolderListItem({
  folder,
  collapsed,
  onToggle,
  children,
}: {
  folder: Folder;
  collapsed: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  const qc = useQueryClient();
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(folder.name);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const renameMut = useMutation({
    mutationFn: (name: string) => renameFolder(folder.id, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["folders"] }),
  });
  const deleteMut = useMutation({
    mutationFn: () => deleteFolder(folder.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["folders"] });
      // Deleting a folder sets every child conversation's folder_id to NULL
      // server-side, so the conversations query is stale.
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  function commitRename() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== folder.name) {
      renameMut.mutate(trimmed);
    }
    setRenaming(false);
  }

  return (
    <div ref={ref}>
      <div className="group relative flex items-center justify-between gap-1 px-1 py-1">
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
            className="flex-1 rounded border border-input bg-background px-2 py-1 text-xs focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
          />
        ) : (
          <button
            onClick={onToggle}
            className="flex flex-1 items-center gap-1 truncate rounded px-1 py-0.5 text-xs font-medium uppercase tracking-wider text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            {collapsed ? (
              <ChevronRight className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
            <span className="truncate">{folder.name}</span>
          </button>
        )}

        {!renaming && (
          <button
            onClick={() => setMenuOpen((o) => !o)}
            className="rounded p-1 text-muted-foreground opacity-0 hover:bg-background group-hover:opacity-100"
            aria-label="Folder actions"
          >
            <MoreHorizontal className="h-3 w-3" />
          </button>
        )}

        {menuOpen && (
          <div className="absolute right-1 top-7 z-20 w-40 rounded-md border border-border bg-popover py-1 text-sm shadow-md">
            <button
              onClick={() => {
                setDraft(folder.name);
                setRenaming(true);
                setMenuOpen(false);
              }}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-muted"
            >
              <Pencil className="h-3.5 w-3.5" /> Rename
            </button>
            <button
              onClick={() => {
                setConfirmDelete(true);
                setMenuOpen(false);
              }}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-destructive hover:bg-muted"
            >
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </button>
          </div>
        )}
      </div>

      {!collapsed && <div className="ml-3 space-y-0.5">{children}</div>}

      <ConfirmDialog
        open={confirmDelete}
        title="Delete folder?"
        body={
          <>
            <span className="font-medium">{folder.name}</span> will be removed.
            Any conversations inside it move back to the root list.
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
