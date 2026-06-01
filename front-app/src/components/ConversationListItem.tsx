import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useMatch, useNavigate } from "react-router-dom";
import { Check, MoreHorizontal, Pencil, Trash2, FolderInput } from "lucide-react";

import {
  Conversation,
  deleteConversation,
  updateConversation,
} from "../api/conversations";
import { Folder } from "../api/folders";

import { ConfirmDialog } from "./ConfirmDialog";


export function ConversationListItem({
  conv,
  folders,
}: {
  conv: Conversation;
  folders: Folder[];
}) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const matchActive = useMatch(`/c/${conv.id}`);
  const isActive = matchActive !== null;

  const [menuOpen, setMenuOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draftTitle, setDraftTitle] = useState(conv.title ?? "");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Outside-click + Escape for the ⋯ menu.
  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setMenuOpen(false);
        setMoveOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMenuOpen(false);
        setMoveOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const updateMut = useMutation({
    mutationFn: (body: Parameters<typeof updateConversation>[1]) =>
      updateConversation(conv.id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conversations"] }),
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteConversation(conv.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      // If the deleted conversation is the open one, bounce to the landing
      // page so we don't render a now-404 route.
      if (isActive) navigate("/");
    },
  });

  function commitRename() {
    const trimmed = draftTitle.trim();
    if (trimmed && trimmed !== conv.title) {
      updateMut.mutate({ title: trimmed });
    }
    setRenaming(false);
  }

  const title = conv.title || "(untitled)";

  return (
    <div ref={ref} className="group relative">
      {renaming ? (
        <input
          autoFocus
          value={draftTitle}
          onChange={(e) => setDraftTitle(e.target.value)}
          onBlur={commitRename}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitRename();
            if (e.key === "Escape") {
              setDraftTitle(conv.title ?? "");
              setRenaming(false);
            }
          }}
          className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        />
      ) : (
        <Link
          to={`/c/${conv.id}`}
          title={title}
          className={
            "flex items-center justify-between gap-2 rounded px-2 py-1.5 text-sm " +
            (isActive ? "bg-muted" : "hover:bg-muted")
          }
        >
          <span className="truncate">{title}</span>
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setMenuOpen((o) => !o);
            }}
            className="rounded p-1 text-muted-foreground opacity-0 hover:bg-background group-hover:opacity-100"
            aria-label="Conversation actions"
          >
            <MoreHorizontal className="h-3.5 w-3.5" />
          </button>
        </Link>
      )}

      {menuOpen && !renaming && (
        <div className="absolute right-1 top-9 z-20 w-44 rounded-md border border-border bg-popover py-1 text-sm shadow-md">
          <button
            onClick={() => {
              setDraftTitle(conv.title ?? "");
              setRenaming(true);
              setMenuOpen(false);
            }}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-muted"
          >
            <Pencil className="h-3.5 w-3.5" /> Rename
          </button>
          <div className="relative">
            <button
              onClick={() => setMoveOpen((o) => !o)}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-muted"
            >
              <FolderInput className="h-3.5 w-3.5" /> Move to folder…
            </button>
            {moveOpen && (
              <div className="absolute right-full top-0 mr-1 w-44 rounded-md border border-border bg-popover py-1 shadow-md">
                <FolderChoice
                  label="(no folder)"
                  active={conv.folder_id === null}
                  onClick={() => {
                    updateMut.mutate({ clear_folder: true });
                    setMenuOpen(false);
                  }}
                />
                {folders.map((f) => (
                  <FolderChoice
                    key={f.id}
                    label={f.name}
                    active={conv.folder_id === f.id}
                    onClick={() => {
                      updateMut.mutate({ folder_id: f.id });
                      setMenuOpen(false);
                    }}
                  />
                ))}
              </div>
            )}
          </div>
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

      <ConfirmDialog
        open={confirmDelete}
        title="Delete conversation?"
        body={
          <>
            <span className="font-medium">{title}</span> and all its messages
            will be permanently removed.
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


function FolderChoice({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm hover:bg-muted"
    >
      <span className="truncate">{label}</span>
      {active && <Check className="h-3.5 w-3.5 text-primary" />}
    </button>
  );
}
