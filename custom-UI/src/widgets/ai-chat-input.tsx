import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { WidgetProps } from "../registry/types.js";
import type { AiChatInputWidget } from "../schema/widgets/ai-chat-input.js";
import type { AgentFile } from "../runtime/agentBridge.js";
import { useAgentUIContext } from "../runtime/context.js";
import { AttachPalette } from "../lib/attach-palette.js";
import {
  CheckIcon,
  fmtSize,
  GlyphIcon,
  SearchIcon,
  tagOf,
  UploadIcon,
  XIcon,
} from "../lib/file-bits.js";

const CANCEL_ACTION = "cancel-run";
const ACCENT = "var(--accent-color, hsl(var(--primary)))";

// Platform-aware shortcut label for the command-palette attach hint.
const SHORTCUT_LABEL =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad|iPod/i.test(navigator.platform || navigator.userAgent || "")
    ? "⌘K"
    : "Ctrl K";

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
  const { dispatcher, agent, pushUserMessage, subscribeContainer } =
    useAgentUIContext();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // Whether a run is in flight — tracked from the agent's status events so the
  // Stop button shows even for runs this composer didn't start (e.g. the first
  // turn fired from the greeting).
  const [running, setRunning] = useState(false);

  const fileSvc = agent?.files;
  const [attached, setAttached] = useState<AgentFile[]>([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [menuQuery, setMenuQuery] = useState("");
  const [library, setLibrary] = useState<AgentFile[] | null>(null);
  const attachRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredLibrary = useMemo(() => {
    const ql = menuQuery.trim().toLowerCase();
    const list = library ?? [];
    return ql ? list.filter((f) => f.name.toLowerCase().includes(ql)) : list;
  }, [library, menuQuery]);

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

  // Open the command-palette attach (keyboard-first variant of the popover).
  const openPalette = useCallback(() => {
    if (!fileSvc) return;
    setMenuOpen(false);
    setPaletteOpen(true);
    fileSvc.listAttached().then(setAttached).catch(() => undefined);
    if (library === null)
      fileSvc.listLibrary().then(setLibrary).catch(() => setLibrary([]));
  }, [fileSvc, library]);

  // ⌘K / Ctrl+K opens it from anywhere in the chat.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openPalette();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [openPalette]);

  useEffect(() => {
    if (!agent) return;
    return subscribeContainer((e) => {
      if (e.kind === "status") setRunning(e.state !== "idle");
    });
  }, [agent, subscribeContainer]);

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
      // The conversation may have just been created (first turn from the
      // greeting, with files attached) — refresh the tray so they show.
      if (fileSvc) fileSvc.listAttached().then(setAttached).catch(() => undefined);
    } finally {
      setSubmitting(false);
    }
  };

  const onCancel = async () => {
    if (!submitting && !running) return;
    try {
      // Prefer the bridge's real cancel (aborts the stream + hits the backend
      // cancel endpoint). Fall back to a `cancel-run` action for hosts that
      // wire cancellation through the dispatcher instead.
      if (agent?.cancel) await agent.cancel();
      else await dispatcher.invoke(CANCEL_ACTION);
    } catch {
      /* nothing to roll back */
    }
  };

  const openMenu = async () => {
    if (!fileSvc) return;
    setMenuOpen((o) => !o);
    // Refresh the tray (the conversation may now exist with linked files).
    fileSvc.listAttached().then(setAttached).catch(() => undefined);
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

  // Palette toggles attachment (attach if absent, detach if present).
  const toggleAttach = async (id: string) => {
    if (!fileSvc) return;
    if (attachedIds.has(id)) {
      await removeAttached(id);
    } else {
      try {
        setAttached(await fileSvc.attach([id]));
      } catch {
        /* ignore */
      }
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      className="hxf rounded-[var(--r-lg,16px)] border border-border bg-card px-4 pb-3 pt-3 transition-colors focus-within:[border-color:var(--accent-color,hsl(var(--primary)))]"
      style={{ boxShadow: "var(--hx-shadow)" }}
    >
      {attached.length > 0 && (
        <div className="attach-pills">
          {attached.map((f) => (
            <span key={f.id} className="apill" title={`${f.name} (${f.mime})`}>
              <span className="fglyph ap-glyph">
                <GlyphIcon name={f.name} size={13} />
              </span>
              <span className="ap-name">{f.name}</span>
              <span className="ap-size">{fmtSize(f.size)}</span>
              <button
                type="button"
                className="ap-x"
                onClick={() => removeAttached(f.id)}
                aria-label={`Remove ${f.name}`}
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
              <div className="attach-menu bottom-full left-0 mb-2">
                <div className="am-search">
                  <SearchIcon />
                  <input
                    value={menuQuery}
                    onChange={(e) => setMenuQuery(e.target.value)}
                    placeholder="Search files to attach"
                    autoFocus
                  />
                </div>
                <button
                  type="button"
                  className="am-upload"
                  onClick={() => inputRef.current?.click()}
                >
                  <span className="au-ic">
                    <UploadIcon />
                  </span>
                  <div>
                    <div className="au-t">Upload new file</div>
                    <div className="au-s">PDF, CSV, code &amp; text</div>
                  </div>
                </button>
                <div className="am-seclbl">From your files</div>
                <div className="am-list">
                  {library === null ? (
                    <div className="am-empty">Loading…</div>
                  ) : filteredLibrary.length === 0 ? (
                    <div className="am-empty">
                      {menuQuery ? `No files match “${menuQuery}”.` : "No files yet."}
                    </div>
                  ) : (
                    filteredLibrary.map((f) => {
                      const on = attachedIds.has(f.id);
                      return (
                        <button
                          key={f.id}
                          type="button"
                          className={"am-row" + (on ? " attached" : "")}
                          onClick={() => pickFromLibrary(f.id)}
                        >
                          <span className="fglyph ar-glyph">
                            <GlyphIcon name={f.name} size={16} />
                          </span>
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div className="ar-name">{f.name}</div>
                            <div className="ar-meta">
                              {tagOf(f.name)} · {fmtSize(f.size)}
                            </div>
                          </div>
                          {on && (
                            <span className="ar-check">
                              <CheckIcon />
                            </span>
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

        {fileSvc && (
          <button
            type="button"
            onClick={openPalette}
            title="Search & attach a file"
            aria-label="Open the attach command palette"
            className="hidden h-7 items-center rounded-md border border-border px-1.5 font-mono text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground sm:flex"
            style={{ fontSize: 10.5, letterSpacing: "0.04em" }}
          >
            {SHORTCUT_LABEL}
          </button>
        )}

        <div className="flex-1" />

        {submitting || running ? (
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

      {paletteOpen && fileSvc && (
        <AttachPalette
          files={(library ?? []).map((f) => ({ id: f.id, name: f.name, size: f.size }))}
          attachedIds={attachedIds}
          onAttach={(f) => toggleAttach(f.id)}
          onUpload={() => {
            setPaletteOpen(false);
            inputRef.current?.click();
          }}
          onClose={() => setPaletteOpen(false)}
        />
      )}
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

