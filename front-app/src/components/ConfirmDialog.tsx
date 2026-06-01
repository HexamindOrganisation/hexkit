import { ReactNode, useEffect } from "react";


/**
 * A minimal modal for destructive confirmations. No portal — relies on a
 * z-index ceiling we control inside the app shell. Closes on backdrop click
 * or Escape.
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

  return (
    <div
      onClick={onCancel}
      className="fixed inset-0 z-30 flex items-center justify-center bg-background/70 p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-lg border border-border bg-card p-5 shadow-lg"
      >
        <h2 className="mb-2 text-sm font-semibold tracking-tight">{title}</h2>
        <div className="mb-5 text-sm text-muted-foreground">{body}</div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded px-3 py-1.5 text-sm hover:bg-muted"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={
              "rounded px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 " +
              (destructive ? "bg-destructive" : "bg-primary")
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
