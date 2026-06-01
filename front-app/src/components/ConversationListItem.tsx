import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Check, FolderInput, MoreHorizontal, Pencil, Trash2 } from "lucide-react";

import {
  Conversation,
  deleteConversation,
  updateConversation,
} from "../api/conversations";
import { Folder } from "../api/folders";
import { AgentGlyph } from "./AgentGlyph";
import { ConfirmDialog } from "./ConfirmDialog";
import { PortalMenu } from "./PortalMenu";

/** dataTransfer type carrying a dragged conversation's id (drop = move). */
export const CONVERSATION_DND_TYPE = "application/x-hexa-conversation-id";

/** Read a dragged conversation id from a drop/dragover event, or "". */
export function readDraggedConversationId(e: React.DragEvent): string {
  return e.dataTransfer.getData(CONVERSATION_DND_TYPE);
}

/** Whether a drag event carries a conversation (for dragover acceptance). */
export function dragHasConversation(e: React.DragEvent): boolean {
  return e.dataTransfer.types.includes(CONVERSATION_DND_TYPE);
}

/**
 * A conversation row in the shared sidebar history: agent-color glyph + title,
 * with a hover ⋯ menu (rename / move-to-folder / delete) rendered in a portal
 * so it never clips or paints behind neighbouring rows, plus HTML5
 * drag-and-drop (drag onto a folder or the root list to move it).
 */
export function ConversationListItem({
  conv,
  folders,
  color,
  active,
}: {
  conv: Conversation;
  folders: Folder[];
  color: string;
  active: boolean;
}) {
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [menuOpen, setMenuOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(conv.title ?? "");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [dragging, setDragging] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);

  const closeMenu = () => {
    setMenuOpen(false);
    setMoveOpen(false);
  };

  const updateMut = useMutation({
    mutationFn: (body: Parameters<typeof updateConversation>[1]) =>
      updateConversation(conv.id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conversations"] }),
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteConversation(conv.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      if (active) navigate("/");
    },
  });

  function commitRename() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== conv.title) updateMut.mutate({ title: trimmed });
    setRenaming(false);
  }

  const title = conv.title || "Untitled session";

  if (renaming) {
    return (
      <input
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commitRename}
        onKeyDown={(e) => {
          if (e.key === "Enter") commitRename();
          if (e.key === "Escape") {
            setDraft(conv.title ?? "");
            setRenaming(false);
          }
        }}
        className="w-full rounded-md border border-[var(--accent-color,hsl(var(--primary)))] bg-background px-2 py-1.5 text-[13.5px] outline-none"
      />
    );
  }

  return (
    <div className="group relative">
      <div
        role="button"
        tabIndex={0}
        draggable
        onDragStart={(e) => {
          e.dataTransfer.setData(CONVERSATION_DND_TYPE, conv.id);
          e.dataTransfer.effectAllowed = "move";
          setDragging(true);
        }}
        onDragEnd={() => setDragging(false)}
        onClick={() => navigate(`/c/${conv.id}`)}
        onKeyDown={(e) => e.key === "Enter" && navigate(`/c/${conv.id}`)}
        title={title}
        className={[
          "hx-srow flex cursor-grab items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm active:cursor-grabbing",
          active ? "bg-secondary" : "hover:bg-secondary/60",
          dragging ? "opacity-40" : "",
        ].join(" ")}
      >
        <AgentGlyph color={color} name={conv.agent_id} size={18} />
        <span className="flex-1 truncate text-[13.5px] text-foreground/90">
          {title}
        </span>
        <button
          ref={btnRef}
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setMenuOpen((o) => !o);
          }}
          className="rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100 aria-expanded:opacity-100"
          aria-expanded={menuOpen}
          aria-label="Conversation actions"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </div>

      <PortalMenu open={menuOpen} onClose={closeMenu} anchorRef={btnRef} width={192}>
        <MenuItem
          icon={<Pencil className="h-3.5 w-3.5" />}
          label="Rename"
          onClick={() => {
            setDraft(conv.title ?? "");
            setRenaming(true);
            closeMenu();
          }}
        />
        <MenuItem
          icon={<FolderInput className="h-3.5 w-3.5" />}
          label="Move to folder…"
          onClick={() => setMoveOpen((o) => !o)}
          expanded={moveOpen}
        />
        {moveOpen && (
          <div className="hx-pop border-y border-border/60 bg-secondary/30 py-1">
            <FolderChoice
              label="No folder"
              active={conv.folder_id === null}
              onClick={() => {
                updateMut.mutate({ clear_folder: true });
                closeMenu();
              }}
            />
            {folders.map((f) => (
              <FolderChoice
                key={f.id}
                label={f.name}
                active={conv.folder_id === f.id}
                onClick={() => {
                  updateMut.mutate({ folder_id: f.id });
                  closeMenu();
                }}
              />
            ))}
          </div>
        )}
        <MenuItem
          icon={<Trash2 className="h-3.5 w-3.5" />}
          label="Delete"
          destructive
          onClick={() => {
            setConfirmDelete(true);
            closeMenu();
          }}
        />
      </PortalMenu>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete conversation?"
        body={
          <>
            <span className="font-medium text-foreground">{title}</span> and all
            its messages will be permanently removed.
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

function MenuItem({
  icon,
  label,
  onClick,
  destructive,
  expanded,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  destructive?: boolean;
  expanded?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={expanded}
      className={[
        "flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-secondary",
        destructive ? "text-destructive" : "",
      ].join(" ")}
    >
      {icon}
      {label}
    </button>
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
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between gap-2 px-3 py-1.5 pl-8 text-left text-[13px] transition-colors hover:bg-secondary"
    >
      <span className="truncate">{label}</span>
      {active && (
        <Check
          className="h-3.5 w-3.5"
          style={{ color: "var(--accent-color, hsl(var(--primary)))" }}
        />
      )}
    </button>
  );
}
