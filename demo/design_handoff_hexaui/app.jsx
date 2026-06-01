/* app.jsx — HexaUI interactive prototype */
const { useState, useRef, useEffect, useCallback } = React;

/* ---- roster (each agent carries its own accent color) ---- */
const AGENTS = [
  { id: "atlas",  name: "Atlas",  role: "Operations copilot",   fw: "LangGraph",     c: "#4f74c9", k: "A" },
  { id: "probe",  name: "Probe",  role: "Research & retrieval",  fw: "LlamaIndex",    c: "#3f9d94", k: "P" },
  { id: "forge",  name: "Forge",  role: "Code & build",          fw: "OpenAI Agents", c: "#56809e", k: "F" },
  { id: "sentry", name: "Sentry", role: "Monitoring & safety",   fw: "AutoGen",       c: "#c79a52", k: "S" },
  { id: "ledger", name: "Ledger", role: "Finance operations",    fw: "CrewAI",        c: "#c2788f", k: "L" },
  { id: "relay",  name: "Relay",  role: "Integrations & RPA",    fw: "Custom",        c: "#c07a55", k: "R" },
];
const byId = (id) => AGENTS.find((a) => a.id === id) || AGENTS[0];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const Glyph = ({ a, size = 24, r = 7, cls = "" }) => (
  <span className={"glyph" + (cls ? " " + cls : "")} style={{ width: size, height: size, borderRadius: r, background: a.c, fontSize: Math.round(size * .46) }}>{a.k}</span>
);

/* ---- canned replies. Paragraph blocks are arrays of styled "runs" so the
        answer can be typed out character-by-character while keeping emphasis. ---- */
const REPLIES = {
  atlas: {
    placeholder: "What should Atlas take on?",
    chips: ["Trace a run", "Summarize a doc", "Draft an automation"],
    steps: ["Querying traces", "Correlating recent deploys"],
    blocks: [
      { runs: [
        { t: "The spike traces to one dependency. " },
        { t: "payment-gateway", b: true },
        { t: " calls jumped from a 40\u00a0ms median to 880\u00a0ms right after deploy " },
        { t: "b3f9c2", m: true, a: true },
        { t: " — it added a synchronous fraud-check hop with no timeout." },
      ] },
      { code: { name: "rollback.yaml", lines: [["target", "checkout-service"], ["action", "rollback"], ["to_revision", '"a17d04"'], ["drain", "30s"]] } },
      { runs: [
        { t: "I can apply this now, or hand off to " },
        { t: "Sentry", b: true },
        { t: " to watch p99 recover before closing the incident." },
      ] },
    ],
  },
  probe: {
    placeholder: "Ask Probe to research or retrieve",
    chips: ["Search the knowledge base", "Compare sources", "Extract from documents"],
    steps: ["Searching knowledge base", "Ranking sources"],
    blocks: [
      { runs: [
        { t: "Across the leading vendors, pricing splits along one axis: " },
        { t: "seats", b: true }, { t: " versus " }, { t: "runs", b: true },
        { t: ". Two anchor to a per-seat subscription with metered overage; the third bills purely per agent execution." },
      ] },
      { runs: [
        { t: "For a wide internal rollout with modest per-user volume, the per-seat vendors stay materially cheaper at scale. I've pulled the three pricing pages into the workspace for reference." },
      ] },
    ],
  },
  forge: {
    placeholder: "Tell Forge what to build",
    chips: ["Refactor a module", "Write tests", "Review a PR"],
    steps: ["Reading CI config", "Estimating job timings"],
    blocks: [
      { runs: [{ t: "I'll split the build into a warm-cache job and parallel test shards so layers are reused between runs:" }] },
      { code: { name: ".ci/build.yaml", lines: [["cache.key", "docker-{{ hash }}"], ["cache.paths", "[/var/lib/docker]"], ["jobs", "[build, test×4, scan]"]] } },
      { runs: [{ t: "Estimated wall-clock drops from ~3m12s to ~1m04s. Want me to open the PR?" }] },
    ],
  },
  sentry: {
    placeholder: "Ask Sentry to watch or audit",
    chips: ["Check agent health", "Review a policy", "Set an alert"],
    steps: ["Polling agent fleet", "Checking alert budgets"],
    blocks: [
      { runs: [
        { t: "All six agents are healthy. One thing to flag: " },
        { t: "Relay", b: true },
        { t: " retried an outbound webhook 4× in the last hour — within budget, but trending up." },
      ] },
      { runs: [{ t: "I've armed an alert to page on-call if the retry rate doubles. No action needed right now." }] },
    ],
  },
  ledger: {
    placeholder: "Ask Ledger about finance ops",
    chips: ["Reconcile invoices", "Forecast spend", "Flag anomalies"],
    steps: ["Loading invoice batch", "Matching purchase orders"],
    blocks: [
      { runs: [{ t: "This batch reconciles cleanly except for two invoices where the PO amount and the received amount diverge by more than the tolerance." }] },
      { runs: [{ t: "Both are from the same vendor and look like a unit-vs-case pricing mismatch. I've drafted a query to send back to procurement." }] },
    ],
  },
  relay: {
    placeholder: "Ask Relay to connect or automate",
    chips: ["Wire an integration", "Map a workflow", "Run a sync"],
    steps: ["Inspecting endpoints", "Validating idempotency"],
    blocks: [
      { runs: [{ t: "I can bridge the two systems with a scheduled sync. The source exposes a clean REST endpoint; the destination needs an idempotency key on each upsert to avoid duplicates." }] },
      { runs: [{ t: "I'll run a dry sync against staging first and report the diff before touching production." }] },
    ],
  },
};

/* render styled runs up to `limit` characters (default: all) */
function renderRuns(runs, limit = Infinity) {
  let count = 0; const out = [];
  for (let i = 0; i < runs.length; i++) {
    if (count >= limit) break;
    const run = runs[i];
    const remain = limit - count;
    const txt = run.t.length > remain ? run.t.slice(0, remain) : run.t;
    count += txt.length;
    const style = run.a ? { color: "var(--accent-2)" } : undefined;
    out.push(<span key={i} className={run.m ? "mono" : undefined} style={style}>{run.b ? <b>{txt}</b> : txt}</span>);
    if (run.t.length > remain) break;
  }
  return out;
}
const blockLen = (b) => b.runs.reduce((a, r) => a + r.t.length, 0);

function CodeBlock({ name, lines }) {
  const { Icons } = window;
  return (
    <div className="codeblk">
      <div className="cb-head"><Icons.doc s={14} /><span className="lbl">{name}</span></div>
      <pre>{lines.map(([k, v], i) => (<div key={i}><span className="k">{k}</span>: <span className="s">{v}</span></div>))}</pre>
    </div>
  );
}

/* ---- agent dropdown menu ---- */
function AgentMenu({ current, onPick, style }) {
  const { Icons } = window;
  const [q, setQ] = useState("");
  const list = AGENTS.filter((a) => (a.name + a.role + a.fw).toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="menu" style={{ width: 320, ...style }} onClick={(e) => e.stopPropagation()}>
      <div className="menu-search">
        <Icons.search s={15} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search agents" autoFocus
          style={{ border: 0, outline: 0, background: "transparent", color: "var(--text)", font: "inherit", flex: 1, fontSize: 13.5 }} />
      </div>
      <div className="menu-list">
        {list.map((a) => (
          <div key={a.id} className={"menu-row" + (a.id === current ? " sel" : "")} onClick={() => onPick(a.id)}>
            <Glyph a={a} size={30} r={8} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <b style={{ fontSize: 13.5 }}>{a.name}</b>
              <div className="role">{a.role} · {a.fw}</div>
            </div>
            {a.id === current && <span style={{ color: "var(--accent)" }}><Icons.check s={16} /></span>}
          </div>
        ))}
        {list.length === 0 && <div style={{ padding: "14px 12px", color: "var(--text-3)", fontSize: 13 }}>No agents match “{q}”.</div>}
      </div>
    </div>
  );
}

/* ---- the composer ---- */
function Composer({ agent, onSend, openMenu, menuOpen, onPickAgent, mini, disabled }) {
  const { Icons } = window;
  const ref = useRef(null);
  const [hasText, setHasText] = useState(false);
  const send = () => {
    const txt = (ref.current.textContent || "").trim();
    if (!txt || disabled) return;
    ref.current.textContent = "";
    setHasText(false);
    onSend(txt);
  };
  const onKey = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };
  return (
    <div className="composer" style={mini ? { boxShadow: "none" } : null}>
      <div ref={ref} className="ce" contentEditable suppressContentEditableWarning
           data-ph={REPLIES[agent.id].placeholder} onKeyDown={onKey}
           onInput={(e) => setHasText(!!(e.currentTarget.textContent || "").trim())} />
      <div className="composer-row">
        <button className="cbtn"><Icons.attach s={17} /></button>
        <span className="spacer" />
        <button className="cbtn" style={{ minWidth: 34, padding: 0 }}><Icons.mic s={17} /></button>
        <button className={"send" + (hasText && !disabled ? "" : " idle")} onClick={send}><Icons.arrowUp s={18} /></button>
      </div>
    </div>
  );
}

/* ---- sidebar ---- */
function Sidebar({ recents, onNew, onOpenRecent, activeRecent, onToggle }) {
  const { Icons } = window;
  return (
    <aside className="sb">
      <div className="sb-head">
        <div className="brand"><HexLogo s={22} /><b>Hexa</b><span className="v">UI</span></div>
        <span className="spacer" />
        <span className="icon-btn" style={{ width: 30, height: 30 }} onClick={onToggle}><Icons.sidebar s={17} /></span>
      </div>
      <div className="sb-body">
        <div className="newchat" onClick={onNew}><span className="ic"><Icons.plus s={17} /></span> New session</div>
        <nav className="nav">
          <div className="nav-item active"><span className="ic"><Icons.chat s={17} /></span> Sessions</div>
          <div className="nav-item"><span className="ic"><Icons.search s={17} /></span> Search</div>
          <div className="nav-item"><span className="ic"><Icons.folder s={17} /></span> Files</div>
          <div className="nav-item"><span className="ic"><Icons.grid s={17} /></span> Workspaces</div>
        </nav>
        <div className="sb-section" style={{ flex: 1, minHeight: 0 }}>
          <span className="lbl">Conversation history</span>
          <div className="recents">
            {recents.map((r, i) => { const ra = byId(r.agent); return (
              <div key={i} className="recent" title={"Talking to " + ra.name}
                   style={activeRecent === i ? { background: "var(--surface-2)", color: "var(--text)" } : null}
                   onClick={() => onOpenRecent(i)}>
                <Glyph a={ra} size={18} r={5} cls="r-glyph" />
                <span className="r-title">{r.title}</span>
              </div>
            ); })}
          </div>
        </div>
      </div>
      <div className="sb-foot">
        <span className="avatar">MK</span>
        <div className="who"><b>Mark</b><span>Hexamind</span></div>
        <span className="spacer" />
        <span className="icon-btn" style={{ width: 28, height: 28 }}><Icons.chevDown s={15} /></span>
      </div>
    </aside>
  );
}

const greetWord = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"; };
const nowTime = () => new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

const RECENTS = [
  { title: "Q3 incident triage", agent: "atlas", user: "checkout-service p99 latency spiked at 14:30. Trace it and tell me what to roll back." },
  { title: "Vendor pricing brief", agent: "probe", user: "Summarize how the three leading vendors price their agent platforms." },
  { title: "CI cache refactor", agent: "forge", user: "Refactor the CI to cache the docker layers between jobs." },
  { title: "Fleet health check", agent: "sentry", user: "Are all agents healthy right now?" },
  { title: "Invoice reconciliation", agent: "ledger", user: "Reconcile this week's invoice batch and flag mismatches." },
  { title: "CRM ↔ billing sync", agent: "relay", user: "Wire a sync between the CRM and the billing system." },
];

function App() {
  const { Icons } = window;
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [agentId, setAgentId] = useState("probe");
  const [messages, setMessages] = useState([]);
  const [menuOpen, setMenuOpen] = useState(null);
  const [activeRecent, setActiveRecent] = useState(null);
  const [pending, setPending] = useState(null);     // live assistant turn
  const [collapsed, setCollapsed] = useState(false);
  const [sessionId, setSessionId] = useState(0);    // bumps to replay greeting
  const threadRef = useRef(null);
  const agent = byId(agentId);
  const inChat = messages.length > 0 || !!pending;

  const accentStyle = t.accent === "agent" ? {
    ["--accent"]: agent.c,
    ["--accent-2"]: agent.c,
    ["--accent-line"]: `color-mix(in srgb, ${agent.c} 44%, transparent)`,
    ["--accent-weak"]: `color-mix(in srgb, ${agent.c} 16%, transparent)`,
  } : null;
  const dataAccent = t.accent === "agent" ? "mono" : t.accent;

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages, pending]);

  const sidebarVisible = t.sidebar === "wide" && !collapsed;

  // One assistant turn: composing (cycling status + skeleton) -> typing answer -> commit.
  const run = useCallback(async (id) => {
    const r = REPLIES[id];
    const steps = r.steps || [];
    setPending({ agent: id, blocks: r.blocks, steps, status: "thinking", statusIx: 0, blockIx: 0, chars: 0, time: nowTime() });
    for (let i = 0; i < steps.length; i++) { setPending((p) => p && { ...p, statusIx: i }); await sleep(780); }
    await sleep(160);
    setPending((p) => p && { ...p, status: "answering", blockIx: 0, chars: 0 });
    for (let j = 0; j < r.blocks.length; j++) {
      const blk = r.blocks[j];
      if (blk.code) {
        setPending((p) => p && { ...p, blockIx: j, chars: 0 });
        await sleep(440);
        setPending((p) => p && { ...p, blockIx: j + 1, chars: 0 });
      } else {
        const len = blockLen(blk);
        setPending((p) => p && { ...p, blockIx: j, chars: 0 });
        for (let c = 0; c <= len; c += 2) { setPending((p) => p && { ...p, chars: c }); await sleep(13); }
        setPending((p) => p && { ...p, chars: len });
        await sleep(240);
        setPending((p) => p && { ...p, blockIx: j + 1, chars: 0 });
      }
    }
    await sleep(200);
    setMessages((m) => [...m, { role: "assistant", agent: id, time: nowTime(), blocks: r.blocks }]);
    setPending(null);
  }, []);

  const send = (text) => {
    if (pending) return;
    setMessages((m) => [...m, { role: "user", text, time: nowTime() }]);
    run(agentId);
  };

  const pickAgent = (id) => { setAgentId(id); setMenuOpen(null); };
  const newSession = () => { setMessages([]); setPending(null); setActiveRecent(null); setMenuOpen(null); setSessionId((s) => s + 1); };
  const openRecent = (i) => {
    const r = RECENTS[i];
    setActiveRecent(i); setAgentId(r.agent); setMenuOpen(null); setPending(null);
    setMessages([{ role: "user", text: r.user, time: "9:14 AM" },
                 { role: "assistant", agent: r.agent, time: "9:14 AM", blocks: REPLIES[r.agent].blocks }]);
  };

  const AgentTrigger = ({ where }) => (
    <div style={{ position: "relative" }}>
      <div className="agent-pick" style={menuOpen === where ? { background: "var(--surface-2)" } : null}
           onClick={(e) => { e.stopPropagation(); setMenuOpen(menuOpen === where ? null : where); }}>
        <span className="ava-wrap" key={agentId} style={{ position: "relative", display: "inline-flex" }}>
          <span className="bloom" />
          <Glyph a={agent} size={22} r={6} cls={pending && pending.status === "thinking" ? "think" : "live"} />
        </span>
        <span>{agent.name}</span>
        <span className="chev"><Icons.chevDown s={16} /></span>
      </div>
      {menuOpen === where && <AgentMenu current={agentId} onPick={pickAgent} style={{ top: "calc(100% + 8px)", left: 0 }} />}
    </div>
  );

  return (
    <div className="hexa app" data-theme={t.theme} data-density={t.density} data-font={t.face} data-accent={dataAccent}
         style={accentStyle} onClick={() => setMenuOpen(null)}>
      {sidebarVisible && (
        <Sidebar recents={RECENTS} onNew={newSession} onOpenRecent={openRecent} activeRecent={activeRecent}
                 onToggle={() => setCollapsed(true)} />
      )}

      <div className="main">
        <div className="topbar">
          {!sidebarVisible && (
            <span className="icon-btn" onClick={(e) => { e.stopPropagation(); setCollapsed(false); setTweak("sidebar", "wide"); }}>
              <Icons.sidebar s={18} />
            </span>
          )}
          <AgentTrigger where="topbar" />
          {inChat && <span style={{ color: "var(--text-3)", fontSize: 14 }}>· {activeRecent != null ? RECENTS[activeRecent].title : "New session"}</span>}
          <span className="spacer" />
          <span className="icon-btn" onClick={(e) => e.stopPropagation()}><Icons.history s={18} /></span>
          <span className="icon-btn" onClick={(e) => e.stopPropagation()}><Icons.dots s={18} /></span>
        </div>

        {!inChat ? (
          <div className="stage" style={{ alignItems: "stretch" }}>
            <div style={{ width: "100%", maxWidth: 720, margin: "0 auto" }}>
              <div style={{ marginBottom: 26 }}>
                <h1 className="greet" key={sessionId} style={{ textAlign: "left", fontSize: "calc(var(--fs-greet) * 1.12)", margin: 0, lineHeight: 1.1 }}>
                  {(greetWord() + ",").split(" ").map((w, i) => (
                    <React.Fragment key={i}><span className="gword" style={{ animationDelay: (i * 0.075) + "s" }}>{w}</span>{" "}</React.Fragment>
                  ))}
                  <br />
                  <span className="gword" style={{ animationDelay: ((greetWord() + ",").split(" ").length * 0.075) + "s" }}>Mark</span>
                </h1>
                <div className="hero-rule draw" key={"r-" + agentId} />
                <div className="talking rise" key={"t-" + agentId} style={{ margin: "16px 0 0" }}>
                  {t.accent === "agent" && <span className="seg" />}
                  Talking to <b>{agent.name}</b> · {agent.role}
                </div>
              </div>
              <Composer agent={agent} onSend={send} menuOpen={menuOpen} disabled={!!pending}
                        openMenu={(w) => setMenuOpen(w)} onPickAgent={pickAgent} />
              <div className="chips" style={{ justifyContent: "flex-start" }}>
                {REPLIES[agentId].chips.map((c, i) => (
                  <div key={i} className="chip" onClick={(e) => { e.stopPropagation(); send(c); }}>{c}</div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="chatwrap">
            {(() => {
              const layout = (window.AgentWidgets && window.AgentWidgets[agentId]) || {};
              const wctx = { pending };
              return (<>
                {layout.top && <div className="agent-top">{layout.top(wctx)}</div>}
                <div className="chatrow">
                  <div className="thread scroll" ref={threadRef}>
                    <div className="thread-inner">
                {messages.map((m, i) => m.role === "user" ? (
                  <div key={i} className="msg user new-pill">
                    <div className="msg-body" style={{ display: "flex", justifyContent: "flex-end" }}>
                      <div className="ucard">{m.text}</div>
                    </div>
                  </div>
                ) : (
                  <div key={i} className="msg assistant new-pill">
                    <Glyph a={byId(m.agent)} size={30} r={8} />
                    <div className="msg-body">
                      <div className="bubble-meta"><b>{byId(m.agent).name}</b><span className="hero-rule" style={{ width: 20, height: 2, margin: 0, background: byId(m.agent).c }} /><span className="t">{m.time}</span></div>
                      {m.blocks.map((b, j) => b.code ? <CodeBlock key={j} {...b.code} /> : <p key={j}>{renderRuns(b.runs)}</p>)}
                      <div className="actions in">
                        <span className="act"><Icons.copy s={15} /></span>
                        <span className="act"><Icons.refresh s={15} /></span>
                      </div>
                    </div>
                  </div>
                ))}
                {pending && (() => {
                  const pa = byId(pending.agent);
                  return (
                    <div className="msg assistant">
                      <Glyph a={pa} size={30} r={8} cls={pending.status === "thinking" ? "think" : ""} />
                      <div className="msg-body">
                        <div className="bubble-meta"><b>{pa.name}</b>
                          <span className="hero-rule" style={{ width: 20, height: 2, margin: 0, background: pa.c }} />
                          <span className="t">{pending.time}</span></div>
                        {pending.status === "thinking" ? (
                          <div className="composing">
                            <div className="goo"><span className="d1" /><span className="d2" /><span className="d3" /></div>
                            <div className="working shimmer">{(pending.steps[pending.statusIx] || "Thinking")}…</div>
                          </div>
                        ) : (
                          pending.blocks.map((b, j) => {
                            if (j > pending.blockIx) return null;
                            if (b.code) return <CodeBlock key={j} {...b.code} />;
                            if (j < pending.blockIx) return <p key={j}>{renderRuns(b.runs)}</p>;
                            return <p key={j}>{renderRuns(b.runs, pending.chars)}<span className="caret" /></p>;
                          })
                        )}
                      </div>
                    </div>
                  );
                })()}
              </div>
            </div>
                  {layout.side && (
                    <aside className="agent-side" style={{ flexBasis: (layout.sideWidth || 340) + "px" }}>
                      <div className="as-head"><span className="lbl">{layout.sideTitle}</span></div>
                      <div className="as-body">{layout.side(wctx)}</div>
                    </aside>
                  )}
                </div>
                <div className="thread-foot">
                  <Composer agent={agent} onSend={send} mini menuOpen={menuOpen} disabled={!!pending}
                            openMenu={(w) => setMenuOpen(w)} onPickAgent={pickAgent} />
                </div>
              </>);
            })()}
          </div>
        )}
      </div>

      {/* ---- Tweaks ---- */}
      <TweaksPanel>
        <TweakSection label="Theme" />
        <TweakRadio label="Mode" value={t.theme} options={["dark", "light"]} onChange={(v) => setTweak("theme", v)} />
        <TweakRadio label="Accent" value={t.accent} options={["agent", "mono", "blue", "sage"]} onChange={(v) => setTweak("accent", v)} />
        <TweakSection label="Layout" />
        <TweakRadio label="Density" value={t.density} options={["comfortable", "compact"]} onChange={(v) => setTweak("density", v)} />
        <TweakRadio label="Sidebar" value={t.sidebar} options={["wide", "hidden"]} onChange={(v) => { setTweak("sidebar", v); setCollapsed(false); }} />
        <TweakSection label="Type" />
        <TweakSelect label="Hero face" value={t.face}
          options={[{ value: "grotesk", label: "Hanken Grotesk" }, { value: "baskerville", label: "Libre Baskerville" }, { value: "source", label: "Source Serif" }]}
          onChange={(v) => setTweak("face", v)} />
      </TweaksPanel>
    </div>
  );
}

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "dark",
  "accent": "agent",
  "density": "comfortable",
  "sidebar": "wide",
  "face": "grotesk"
}/*EDITMODE-END*/;

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
