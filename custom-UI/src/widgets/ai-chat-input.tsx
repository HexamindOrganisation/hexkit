import { useEffect, useRef, useState } from "react";
import type { WidgetProps } from "../registry/types.js";
import type { AiChatInputWidget } from "../schema/widgets/ai-chat-input.js";
import type { AgentFile } from "../runtime/agentBridge.js";
import { useAgentUIContext } from "../runtime/context.js";

const CANCEL_ACTION = "cancel-run";
const ACCENT = "var(--accent-color, hsl(var(--primary)))";

/**
 * The constant HexaUI composer: one quiet field on a surface card — attach on
 * the left, send on the right. When the bridge exposes a file capability, the
 * attach button opens a menu to upload a new file or reuse one from the
 * library; attached files persist on the conversation and show as a tray of
 * chips above the field. Enter submits, Shift+Enter newlines.
 */
export function AiChatInputWidgetComponent({
  props,
}: WidgetProps<AiChatInputWidget>): JSX.Element {
  const { dispatcher, agent, pushUserMessage } = useAgentUIContext();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fileSvc = agent?.files;
  const [attached, setAttached] = useState<AgentFile[]>([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [library, setLibrary] = useState<AgentFile[] | null>(null);
  const attachRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const canFallback = !agent && (dispatcher.has?.("user-submit") ?? false);
  const inert = !agent && !canFallback;
  const hasText = text.trim().length > 0;

  useEffect(() => {
    if (fileSvc) fileSvc.listAttached().then(setAttached).catch(() => undefined);
  }, [fileSvc]);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (attachRef.current && !attachRef.current.contains(e.target as Node))
        setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  const attachedIds = new Set(attached.map((a) => a.id));

  const onSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (submitting) return;
    const t = text.trim();
    if (!t) return;
    setSubmitting(true);
    try {
      pushUserMessage(t);
      if (agent) await agent.onUserSubmit(t);
      else if (canFallback) await dispatcher.invoke("user-submit", { text: t });
      setText("");
    } finally {
      setSubmitting(false);
    }
  };

  const onCancel = async () => {
    if (!submitting) return;
    try {
      await dispatcher.invoke(CANCEL_ACTION);
    } catch {
      /* nothing to roll back */
    }
  };

  const openMenu = async () => {
    if (!fileSvc) return;
    setMenuOpen((o) => !o);
    if (library === null) {
      try {
        setLibrary(await fileSvc.listLibrary());
      } catch {
        setLibrary([]);
      }
    }
  };

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (!picked.length || !fileSvc) return;
    setMenuOpen(false);
    try {
      const created = await fileSvc.upload(picked);
      setAttached(await fileSvc.attach(created.map((c) => c.id)));
      setLibrary(null); // library changed; refetch next open
    } catch {
      /* surfaced elsewhere */
    }
  };

  const pickFromLibrary = async (id: string) => {
    if (!fileSvc) return;
    setMenuOpen(false);
    try {
      setAttached(await fileSvc.attach([id]));
    } catch {
      /* ignore */
    }
  };

  const removeAttached = async (id: string) => {
    if (!fileSvc) return;
    try {
      await fileSvc.detach(id);
      setAttached((prev) => prev.filter((a) => a.id !== id));
    } catch {
      /* ignore */
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-[var(--r-lg,16px)] border border-border bg-card px-4 pb-3 pt-3 transition-colors focus-within:[border-color:var(--accent-color,hsl(var(--primary)))]"
      style={{ boxShadow: "var(--hx-shadow)" }}
    >
      {attached.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {attached.map((f) => (
            <span
              key={f.id}
              className="flex items-center gap-1.5 rounded-md border border-border bg-secondary/60 py-1 pl-2 pr-1 text-xs"
              title={`${f.name} (${f.mime})`}
            >
              <FileIcon />
              <span className="max-w-[160px] truncate">{f.name}</span>
              <button
                type="button"
                onClick={() => removeAttached(f.id)}
                aria-label={`Remove ${f.name}`}
                className="rounded p-0.5 text-muted-foreground hover:bg-card hover:text-foreground"
              >
                <XIcon />
              </button>
            </span>
          ))}
        </div>
      )}

      <textarea
        className="block max-h-48 w-full resize-none bg-transparent px-1 text-[15px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground disabled:opacity-60"
        rows={props.rows ?? 1}
        placeholder={
          inert ? "Input disabled — no bridge" : props.placeholder ?? "Ask anything…"
        }
        value={text}
        disabled={inert || submitting}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void onSubmit();
          }
        }}
      />

      <div className="mt-2 flex items-center gap-1">
        {fileSvc && (
          <div ref={attachRef} className="relative">
            <input ref={inputRef} type="file" multiple hidden onChange={onUpload} />
            <IconButton label="Attach files" onClick={openMenu}>
              <PaperclipIcon />
            </IconButton>
            {menuOpen && (
              <div className="hx-pop absolute bottom-full left-0 z-50 mb-2 w-60 overflow-hidden rounded-lg border border-border bg-popover py-1 text-sm shadow-xl">
                <button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-secondary"
                >
                  <UploadIcon /> Upload file…
                </button>
                <div className="my-1 border-t border-border/60" />
                <div className="px-3 pb-1 font-mono text-[10.5px] uppercase tracking-wide text-muted-foreground">
                  From library
                </div>
                <div className="max-h-56 overflow-auto">
                  {library === null ? (
                    <div className="px-3 py-2 text-xs text-muted-foreground">Loading…</div>
                  ) : library.length === 0 ? (
                    <div className="px-3 py-2 text-xs text-muted-foreground">No files yet.</div>
                  ) : (
                    library.map((f) => {
                      const on = attachedIds.has(f.id);
                      return (
                        <button
                          key={f.id}
                          type="button"
                          disabled={on}
                          onClick={() => pickFromLibrary(f.id)}
                          className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-secondary disabled:opacity-50"
                        >
                          <FileIcon />
                          <span className="flex-1 truncate text-[13px]">{f.name}</span>
                          {on && (
                            <span className="text-[11px] text-muted-foreground">attached</span>
                          )}
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="flex-1" />

        {submitting ? (
          <button
            type="button"
            onClick={onCancel}
            aria-label="Stop"
            className="flex h-9 w-9 items-center justify-center rounded-full text-white"
            style={{ background: ACCENT }}
          >
            <StopIcon />
          </button>
        ) : (
          <button
            type="submit"
            disabled={inert || !hasText}
            aria-label={props.submit_label ?? "Send"}
            className="flex h-9 w-9 items-center justify-center rounded-full transition-colors disabled:cursor-not-allowed"
            style={
              hasText
                ? { background: ACCENT, color: "hsl(var(--background))" }
                : { background: "hsl(var(--muted))", color: "hsl(var(--muted-foreground))" }
            }
          >
            <SendIcon />
          </button>
        )}
      </div>
    </form>
  );
}

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick?: () => void;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
    >
      {children}
    </button>
  );
}

function SendIcon(): JSX.Element {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="h-4 w-4">
      <path d="M8 13V3" />
      <path d="M4 7l4-4 4 4" />
    </svg>
  );
}

function StopIcon(): JSX.Element {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden className="h-3 w-3">
      <rect x="3" y="3" width="10" height="10" rx="1.5" />
    </svg>
  );
}

function PaperclipIcon(): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="h-[18px] w-[18px]">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  );
}

function UploadIcon(): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="h-4 w-4">
      <path d="M12 16V4" />
      <path d="M7 9l5-5 5 5" />
      <path d="M5 20h14" />
    </svg>
  );
}

function FileIcon(): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="h-3.5 w-3.5 shrink-0 text-muted-foreground">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

function XIcon(): JSX.Element {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden className="h-3 w-3">
      <path d="M4 4l8 8M12 4l-8 8" />
    </svg>
  );
}
