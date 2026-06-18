import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { WidgetProps } from "../registry/types.js";
import type { DropdownWidget } from "../schema/widgets/dropdown.js";
import { useAgentUIContext } from "../runtime/context.js";
import { cn } from "../lib/utils.js";

/**
 * A single-select dropdown. Choosing an option invokes that option's `action`
 * and re-pulls the widgets in its `refresh` list — the same `action` + `refresh`
 * mechanism the button-group uses. Built as a custom popover (not a native
 * `<select>`) so the menu and items follow the app's design tokens.
 *
 * The menu is rendered through a portal into the nearest `.au-root` and
 * positioned `fixed`: the widget host clips with `overflow: auto`, which would
 * otherwise cut off both the menu and the trigger's accent outline. Portaling
 * into `.au-root` (not `document.body`) keeps the inline agent color / dark-mode
 * vars that the theme bridge sets there. The trigger's active state uses a
 * border color (inside the box), not a ring (which would also be clipped).
 *
 * The selected value is local UI state; the backend stays the source of truth.
 */
export function DropdownWidgetComponent({
  props,
  dispatcher,
}: WidgetProps<DropdownWidget>): JSX.Element {
  const { requestRefresh } = useAgentUIContext();
  const initial = props.default ?? props.options[0]?.value ?? "";
  const [value, setValue] = useState<string>(initial);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const selected = props.options.find((o) => o.value === value);

  const place = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    setPos({ top: r.bottom + 4, left: r.left, width: r.width });
  }, []);

  // While open: close on outside click / Escape, and keep the menu pinned to the
  // trigger if the page scrolls or resizes (capture catches inner scrolls too).
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (triggerRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, place]);

  const toggle = () => {
    if (open) {
      setOpen(false);
    } else {
      place();
      setOpen(true);
    }
  };

  const choose = useCallback(
    (next: string) => {
      setOpen(false);
      const opt = props.options.find((o) => o.value === next);
      if (!opt) return;
      setValue(next);
      dispatcher
        .invoke(opt.action, opt.args)
        .then(() => {
          if (opt.refresh?.length) requestRefresh(opt.refresh);
        })
        .catch(() => {
          /* action errors surface via the backend / diagnostics */
        });
    },
    [props.options, dispatcher, requestRefresh],
  );

  const portalTarget =
    (triggerRef.current?.closest(".au-root") as HTMLElement | null) ??
    (typeof document !== "undefined" ? document.body : null);

  return (
    <div className="flex items-center gap-2 text-sm">
      {props.label && (
        <span className="text-muted-foreground">{props.label}</span>
      )}
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={toggle}
        className={cn(
          "flex min-w-[8rem] items-center justify-between gap-2 rounded-md border bg-background px-3 py-1.5 text-sm text-foreground transition-colors",
          "hover:bg-accent focus:outline-none focus-visible:border-ring",
          open ? "border-ring" : "border-border",
        )}
      >
        <span className={cn(!selected && "text-muted-foreground")}>
          {selected?.label ?? props.placeholder ?? "Select…"}
        </span>
        <ChevronIcon open={open} />
      </button>

      {open &&
        pos &&
        portalTarget &&
        createPortal(
          <div
            ref={menuRef}
            role="listbox"
            style={{
              position: "fixed",
              top: pos.top,
              left: pos.left,
              minWidth: pos.width,
              zIndex: 1000,
            }}
            className="overflow-hidden rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md"
          >
            {props.options.map((o) => {
              const active = o.value === value;
              return (
                <button
                  key={o.value}
                  type="button"
                  role="option"
                  aria-selected={active}
                  onClick={() => choose(o.value)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm transition-colors",
                    "hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:outline-none",
                    active && "font-medium",
                  )}
                >
                  <CheckIcon
                    className={active ? "opacity-100" : "opacity-0"}
                    color="var(--accent-color, hsl(var(--primary)))"
                  />
                  <span className="flex-1 whitespace-nowrap">{o.label}</span>
                </button>
              );
            })}
          </div>,
          portalTarget,
        )}
    </div>
  );
}

function ChevronIcon({ open }: { open: boolean }): JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className="text-muted-foreground transition-transform"
      style={{ width: 14, height: 14, transform: open ? "rotate(180deg)" : undefined }}
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

function CheckIcon({
  className,
  color,
}: {
  className?: string;
  color?: string;
}): JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke={color ?? "currentColor"}
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={className}
      style={{ width: 14, height: 14, flexShrink: 0 }}
    >
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}
