import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/**
 * A dropdown menu rendered in a portal on `document.body`, positioned (fixed)
 * under an anchor element. Portaling escapes both the sidebar's stacking order
 * (so it never paints behind later rows) and any `overflow: hidden` container
 * (so a conversation menu inside a folder isn't clipped). Closes on
 * outside-click, Escape, or scroll.
 */
export function PortalMenu({
  open,
  onClose,
  anchorRef,
  width = 192,
  children,
}: {
  open: boolean;
  onClose: () => void;
  anchorRef: React.RefObject<HTMLElement>;
  width?: number;
  children: React.ReactNode;
}) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  useLayoutEffect(() => {
    if (!open || !anchorRef.current) {
      setPos(null);
      return;
    }
    const r = anchorRef.current.getBoundingClientRect();
    const left = Math.max(
      8,
      Math.min(r.right - width, window.innerWidth - width - 8),
    );
    setPos({ top: r.bottom + 4, left });
  }, [open, anchorRef, width]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (anchorRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const onScroll = () => onClose();
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    // capture-phase so a scroll in any ancestor (the sidebar nav) closes it
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open, anchorRef, onClose]);

  if (!open || !pos) return null;

  return createPortal(
    <div
      ref={menuRef}
      style={{ top: pos.top, left: pos.left, width }}
      className="hx-pop fixed z-[100] overflow-hidden rounded-lg border border-border bg-popover py-1 text-sm text-foreground shadow-xl"
    >
      {children}
    </div>,
    document.body,
  );
}
