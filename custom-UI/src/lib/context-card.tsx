import { useEffect, useRef, useState, type ReactNode } from "react";
import { useAgentUIContext } from "../runtime/context.js";

/**
 * Frame for a display widget (table / markdown) that can toggle its content
 * into the conversation's model context. Ported from the HexaUI "Context Toggle"
 * design: a header (icon + caption + the pill switch) over the widget body; when
 * on, the card lights to the agent accent with a one-shot scan/glow.
 *
 * The toggle drives the host's `ContextService` (`agent.context`): on →
 * `set(key, {label, mime, text})`, off → `remove(key)`. State is restored on
 * mount from `list()`, and re-synced live while on as `text` changes. When the
 * host exposes no context capability, the toggle is hidden (the frame remains).
 */
export function ContextCard({
  widgetKey,
  caption,
  mime,
  text,
  headerAction,
  children,
}: {
  /** Stable per-widget key (the widget name). */
  widgetKey: string;
  /** Header label, also the context item's label shown to the model. */
  caption: string;
  mime: string;
  /** Current widget content as text; "" means "nothing to add yet". */
  text: string;
  /** Optional control rendered in the header, before the context toggle. */
  headerAction?: ReactNode;
  children: ReactNode;
}): JSX.Element {
  const { agent } = useAgentUIContext();
  const ctx = agent?.context;
  const [on, setOn] = useState(false);
  const [scanning, setScanning] = useState(false);
  const scanTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Restore toggle state for this conversation (the provider remounts per
  // conversation, so this re-runs on conversation switch).
  useEffect(() => {
    if (!ctx) return;
    let cancelled = false;
    ctx
      .list()
      .then((keys) => {
        if (!cancelled && keys.includes(widgetKey)) setOn(true);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [ctx, widgetKey]);

  // Sync content while on (initial + live). Never push empty text — that would
  // clobber the stored content before a data_source has loaded. Toggling OFF is
  // handled in the click handler, not here, so mounting never deletes.
  useEffect(() => {
    if (!ctx || !on || !text) return;
    ctx.set(widgetKey, { label: caption, mime, text }).catch(() => undefined);
  }, [ctx, on, text, widgetKey, caption, mime]);

  useEffect(
    () => () => {
      if (scanTimer.current) clearTimeout(scanTimer.current);
    },
    [],
  );

  const toggle = () => {
    if (!ctx) return;
    setOn((v) => {
      const next = !v;
      if (next) {
        setScanning(true);
        if (scanTimer.current) clearTimeout(scanTimer.current);
        scanTimer.current = setTimeout(() => setScanning(false), 700);
        // The sync effect performs `set` once `on` flips (and text is present).
      } else {
        ctx.remove(widgetKey).catch(() => undefined);
      }
      return next;
    });
  };

  return (
    <div
      className={"hxf w-ctx" + (on ? " on" : "") + (scanning ? " scanning" : "")}
    >
      <div className="w-ctx-head">
        <span className="ch-ic">{iconForMime(mime)}</span>
        <span className="ch-title">{caption}</span>
        <span className="spacer" style={{ flex: 1 }} />
        {headerAction}
        {ctx && (
          <button
            type="button"
            className={"ctx-toggle" + (on ? " on" : "")}
            onClick={toggle}
            aria-pressed={on}
            disabled={!on && !text}
            title={
              on
                ? "Remove this widget from the model's context"
                : "Include this widget's content in the model's context"
            }
          >
            <span className="ct-ic">
              <LayersIcon />
            </span>
            <span className="ct-label">
              <span className="off-t">Add to context</span>
              <span className="on-t">
                <CheckIcon /> In context
              </span>
            </span>
            <span className="ctx-sw">
              <span className="knob" />
            </span>
          </button>
        )}
      </div>
      <div className="w-ctx-body">
        <div className="ctx-scan" aria-hidden>
          <span className="bar" />
        </div>
        {children}
      </div>
    </div>
  );
}

function iconForMime(mime: string): ReactNode {
  if (mime.includes("csv") || mime.includes("tab-separated")) return <SheetIcon />;
  return <DocIcon />;
}

function LayersIcon({ size = 15 }: { size?: number }): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden style={{ width: size, height: size }}>
      <path d="M12 3l9 5-9 5-9-5 9-5z" />
      <path d="M3 13l9 5 9-5" />
    </svg>
  );
}

function CheckIcon({ size = 13 }: { size?: number }): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden style={{ width: size, height: size }}>
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

function SheetIcon({ size = 15 }: { size?: number }): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden style={{ width: size, height: size }}>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M3 15h18M9 3v18M15 3v18" />
    </svg>
  );
}

function DocIcon({ size = 15 }: { size?: number }): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden style={{ width: size, height: size }}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}
