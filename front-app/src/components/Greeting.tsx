import { Fragment, useEffect, useRef, useState } from "react";
import { ArrowUp, FileText, Paperclip, Upload, X } from "lucide-react";

import type { AgentSummary } from "../api/agents";
import { listFiles, uploadFile, type FileMeta } from "../api/files";

const ACCENT = "var(--accent-color, hsl(var(--primary)))";

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
  const [library, setLibrary] = useState<FileMeta[] | null>(null);
  const attachRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasText = text.trim().length > 0;

  const words = `${greetWord()}, dev01`.split(" ");

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (attachRef.current && !attachRef.current.contains(e.target as Node))
        setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

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
          className="mt-7 rounded-[var(--r-lg,16px)] border border-border bg-card px-4 pb-3 pt-3.5 transition-colors focus-within:[border-color:var(--accent-color,hsl(var(--primary)))]"
          style={{ boxShadow: "var(--hx-shadow)" }}
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          {pending.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {pending.map((f) => (
                <span
                  key={f.id}
                  className="flex items-center gap-1.5 rounded-md border border-border bg-secondary/60 py-1 pl-2 pr-1 text-xs"
                  title={f.name}
                >
                  <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <span className="max-w-[160px] truncate">{f.name}</span>
                  <button
                    type="button"
                    onClick={() => setPending((p) => p.filter((x) => x.id !== f.id))}
                    aria-label={`Remove ${f.name}`}
                    className="rounded p-0.5 text-muted-foreground hover:bg-card hover:text-foreground"
                  >
                    <X className="h-3 w-3" />
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
                <div className="hx-pop absolute bottom-full left-0 z-50 mb-2 w-60 overflow-hidden rounded-lg border border-border bg-popover py-1 text-sm shadow-xl">
                  <button
                    type="button"
                    onClick={() => inputRef.current?.click()}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-secondary"
                  >
                    <Upload className="h-4 w-4" /> Upload file…
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
                        const on = pendingIds.has(f.id);
                        return (
                          <button
                            key={f.id}
                            type="button"
                            disabled={on}
                            onClick={() => {
                              addPending(f);
                              setMenuOpen(false);
                            }}
                            className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-secondary disabled:opacity-50"
                          >
                            <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                            <span className="flex-1 truncate text-[13px]">{f.name}</span>
                            {on && <span className="text-[11px] text-muted-foreground">added</span>}
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              )}
            </div>
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
    </div>
  );
}
