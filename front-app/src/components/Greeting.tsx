import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Check, Paperclip, Search, Upload, X } from "lucide-react";
import { AttachPalette } from "agent-ui";

import type { AgentSummary } from "../api/agents";
import { listFiles, uploadFile, type FileMeta } from "../api/files";
import { useAuth } from "../auth/AuthContext";
import { FileGlyph, fmtSize, relTime, tagOf } from "../lib/fileFx";

const ACCENT = "var(--accent-color, hsl(var(--primary)))";

// Platform-aware shortcut label for the command-palette attach hint.
const SHORTCUT_LABEL =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad|iPod/i.test(navigator.platform || navigator.userAgent || "")
    ? "⌘K"
    : "Ctrl K";

function greetWord(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

/**
 * The empty-state / new-session screen (per the HexaUI handoff): a grotesk
 * greeting that rises in word-by-word, an accent hero-rule, a "Talking to
 * {agent}" line, and the composer. Stays clean — the agent's widgets only
 * appear once a conversation is active. Sending hands the text + any pending
 * attachments up to the host, which mounts the chat, links the files to the
 * new conversation, and streams the reply.
 */
export function Greeting({
  agent,
  sessionKey,
  onSend,
}: {
  agent: AgentSummary;
  /** Changes per new session so the entrance animation replays. */
  sessionKey: string;
  onSend: (text: string, fileIds: string[]) => void;
}) {
  const [text, setText] = useState("");
  const [pending, setPending] = useState<FileMeta[]>([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [menuQuery, setMenuQuery] = useState("");
  const [library, setLibrary] = useState<FileMeta[] | null>(null);
  const attachRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasText = text.trim().length > 0;
  const { user } = useAuth();
  const handle = user?.name?.trim() || user?.email.split("@")[0] || "there";

  const filteredLibrary = useMemo(() => {
    const ql = menuQuery.trim().toLowerCase();
    const list = library ?? [];
    return ql ? list.filter((f) => f.name.toLowerCase().includes(ql)) : list;
  }, [library, menuQuery]);

  const words = `${greetWord()}, ${handle}`.split(" ");

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
    setMenuOpen(false);
    setPaletteOpen(true);
    if (library === null) listFiles().then(setLibrary).catch(() => setLibrary([]));
  }, [library]);

  // ⌘K / Ctrl+K opens it from anywhere on the greeting.
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

  const submit = () => {
    const t = text.trim();
    if (t) onSend(t, pending.map((p) => p.id));
  };

  const openMenu = async () => {
    setMenuOpen((o) => !o);
    if (library === null) {
      try {
        setLibrary(await listFiles());
      } catch {
        setLibrary([]);
      }
    }
  };

  const addPending = (f: FileMeta) =>
    setPending((prev) => (prev.some((p) => p.id === f.id) ? prev : [...prev, f]));

  const togglePending = (f: FileMeta) =>
    setPending((prev) =>
      prev.some((p) => p.id === f.id)
        ? prev.filter((p) => p.id !== f.id)
        : [...prev, f],
    );

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (!picked.length) return;
    setMenuOpen(false);
    for (const file of picked) {
      try {
        addPending(await uploadFile(file));
      } catch {
        /* ignore */
      }
    }
    setLibrary(null);
  };

  const pendingIds = new Set(pending.map((p) => p.id));

  return (
    <div className="flex h-full items-center justify-center overflow-auto p-6">
      <div className="w-full max-w-[720px]">
        <h1
          key={sessionKey}
          className="text-[clamp(34px,5vw,47px)] font-semibold leading-[1.1] tracking-[-0.025em] text-foreground"
          style={{
            fontFamily:
              "var(--font-ui, 'Hanken Grotesk', ui-sans-serif, system-ui, sans-serif)",
          }}
        >
          {words.map((w, i) => (
            <Fragment key={i}>
              <span className="hx-gword" style={{ animationDelay: `${i * 0.075}s` }}>
                {w}
              </span>{" "}
            </Fragment>
          ))}
        </h1>

        <div key={`r-${agent.id}`} className="hx-hero-rule mt-[18px]" />

        <div
          key={`t-${agent.id}`}
          className="mt-4 flex items-center gap-2 text-[12.5px] text-[var(--hx-text-3,hsl(var(--muted-foreground)))]"
        >
          <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: ACCENT }} />
          <span>
            Talking to <span className="font-semibold text-foreground/80">{agent.name}</span> ·{" "}
            {agent.role}
          </span>
        </div>

        <form
          className="hxf mt-7 rounded-[var(--r-lg,16px)] border border-border bg-card px-4 pb-3 pt-3.5 transition-colors focus-within:[border-color:var(--accent-color,hsl(var(--primary)))]"
          style={{ boxShadow: "var(--hx-shadow)" }}
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          {pending.length > 0 && (
            <div className="attach-pills">
              {pending.map((f) => (
                <span key={f.id} className="apill" title={f.name}>
                  <FileGlyph name={f.name} size={22} className="fglyph ap-glyph" />
                  <span className="ap-name">{f.name}</span>
                  <span className="ap-size">{fmtSize(f.size)}</span>
                  <button
                    type="button"
                    className="ap-x"
                    onClick={() => setPending((p) => p.filter((x) => x.id !== f.id))}
                    aria-label={`Remove ${f.name}`}
                  >
                    <X style={{ width: 14, height: 14 }} />
                  </button>
                </span>
              ))}
            </div>
          )}

          <textarea
            autoFocus
            rows={1}
            value={text}
            placeholder={`Ask ${agent.name}…`}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            className="block max-h-48 w-full resize-none bg-transparent px-1 text-[15px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground"
          />
          <div className="mt-2 flex items-center gap-1">
            <div ref={attachRef} className="relative">
              <input ref={inputRef} type="file" multiple hidden onChange={onUpload} />
              <button
                type="button"
                onClick={openMenu}
                aria-label="Attach files"
                className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
              >
                <Paperclip className="h-[18px] w-[18px]" />
              </button>
              {menuOpen && (
                <div className="attach-menu bottom-full left-0 mb-2">
                  <div className="am-search">
                    <Search style={{ width: 15, height: 15 }} />
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
                      <Upload style={{ width: 17, height: 17 }} />
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
                        const on = pendingIds.has(f.id);
                        return (
                          <button
                            key={f.id}
                            type="button"
                            className={"am-row" + (on ? " attached" : "")}
                            onClick={() => {
                              addPending(f);
                              setMenuOpen(false);
                            }}
                          >
                            <FileGlyph name={f.name} size={30} className="fglyph ar-glyph" />
                            <div style={{ minWidth: 0, flex: 1 }}>
                              <div className="ar-name">{f.name}</div>
                              <div className="ar-meta">
                                {tagOf(f.name)} · {fmtSize(f.size)} · {relTime(f.created_at)}
                              </div>
                            </div>
                            {on && (
                              <span className="ar-check">
                                <Check style={{ width: 17, height: 17 }} />
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
            <div className="flex-1" />
            <button
              type="submit"
              disabled={!hasText}
              aria-label="Send"
              className="flex h-9 w-9 items-center justify-center rounded-full transition-colors disabled:cursor-not-allowed"
              style={
                hasText
                  ? { background: ACCENT, color: "hsl(var(--background))" }
                  : { background: "hsl(var(--muted))", color: "hsl(var(--muted-foreground))" }
              }
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          </div>
        </form>
      </div>

      {paletteOpen && (
        <AttachPalette
          files={(library ?? []).map((f) => ({
            id: f.id,
            name: f.name,
            size: f.size,
            created_at: f.created_at,
          }))}
          attachedIds={pendingIds}
          onAttach={(f) => {
            const meta = (library ?? []).find((x) => x.id === f.id);
            if (meta) togglePending(meta);
          }}
          onUpload={() => {
            setPaletteOpen(false);
            inputRef.current?.click();
          }}
          onClose={() => setPaletteOpen(false)}
        />
      )}
    </div>
  );
}
