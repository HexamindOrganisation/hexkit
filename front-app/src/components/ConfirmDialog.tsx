import { CSSProperties, ReactNode, useEffect } from "react";
import { createPortal } from "react-dom";


/**
 * A minimal modal for destructive confirmations. Rendered in a portal on
 * `document.body` so it always overlays the whole app, regardless of where it's
 * mounted (e.g. inside a folder's clipped/transformed sidebar subtree). Closes
 * on backdrop click or Escape.
 */
export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = "Confirm",
  destructive = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  body: ReactNode;
  confirmLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return createPortal(
    <div
      onClick={onCancel}
      className="fixed inset-0 z-[200] flex items-center justify-center bg-background/60 p-4 backdrop-blur-sm"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ "--hx-pop-origin": "center", boxShadow: "var(--hx-shadow)" } as CSSProperties}
        className="hx-pop w-full max-w-sm rounded-xl border border-border bg-card p-5"
      >
        <h2 className="mb-2 text-sm font-semibold tracking-tight">{title}</h2>
        <div className="mb-5 text-sm text-muted-foreground">{body}</div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="hx-srow rounded-md px-3 py-1.5 text-sm hover:bg-secondary"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={
              "hx-srow rounded-md px-3 py-1.5 text-sm font-medium hover:opacity-90 " +
              (destructive
                ? "bg-destructive text-white"
                : "bg-primary text-primary-foreground")
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
