/* widgets.jsx — HexaUI-styled specimens of every native agent-ui widget.
   Pulls shared helpers (AGENTS, Glyph, Frame, Note, SpecHead) from window,
   set up by reference.jsx. Each card shows the widget's `type:` and a short
   note on how it inherits the HexaUI tokens. */
const { Icons, Glyph, AGENTS, byId, Frame, Note, SpecHead } = window;

/* a labeled widget host wrapper (the default chrome) */
const Host = ({ title, chromeless, children, style }) => (
  <div className={"w-host" + (chromeless ? " chromeless" : "")} style={style}>
    {title && <div className="w-head"><span className="lbl">{title}</span></div>}
    {children}
  </div>
);

/* ============================================================
   button-group
   ============================================================ */
function ButtonGroupW({ theme = "dark", agentId = "atlas" }) {
  const a = byId(agentId);
  const Btn = ({ v = "default", children, sz }) => <button className={"w-btn w-btn-" + v + (sz ? " " + sz : "")}>{children}</button>;
  return (
    <Frame theme={theme} accent="mono" pad={36} style={{ "--accent": a.c, "--accent-2": a.c }}>
      <SpecHead k='type: "button-group"' t="Button group"
        d="The six shadcn variants, mapped to HexaUI tokens. Only the primary (default) action carries the agent fill; everything else stays quiet." />
      <Host title="Variants">
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <Btn v="default">Run job</Btn>
          <Btn v="secondary">Duplicate</Btn>
          <Btn v="outline">Settings</Btn>
          <Btn v="ghost">Cancel</Btn>
          <Btn v="destructive">Delete all</Btn>
          <Btn v="link">Learn more</Btn>
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginTop: 16 }}>
          <Btn v="default" sz="sm">Small</Btn>
          <Btn v="default">Default</Btn>
          <Btn v="default" sz="lg">Large</Btn>
          <button className="w-btn w-btn-outline icon"><Icons.refresh s={16} /></button>
        </div>
      </Host>
    </Frame>
  );
}

/* ============================================================
   metrics
   ============================================================ */
function MetricsW({ theme = "dark", agentId = "ledger" }) {
  const a = byId(agentId);
  const Cell = ({ label, value, delta, hint }) => (
    <div className="w-metric">
      <div className="m-label">{label}</div>
      <div className="m-row">
        <div className="m-value">{value}</div>
        {delta != null && <span className={"w-delta " + (delta > 0 ? "up" : "down")}>{delta > 0 ? "▲" : "▼"} {Math.abs(delta).toLocaleString()}</span>}
      </div>
      {hint && <div className="m-hint">{hint}</div>}
    </div>
  );
  return (
    <Frame theme={theme} accent="mono" pad={36} style={{ "--accent": a.c, "--accent-2": a.c }}>
      <SpecHead k='type: "metrics"' t="Metrics strip"
        d="Stat cards bound to a data source. Tabular-figure values, an uppercase micro-label, and a delta badge (sage up / rose down). Live when the source supports subscribe." />
      <Host chromeless>
        <div className="w-metrics" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
          <Cell label="Tokens" value="18,420" delta={1240} hint="this session" />
          <Cell label="Cost" value="$0.0732" />
          <Cell label="p95 latency" value="312ms" hint="rolling 5 min" />
          <Cell label="Success rate" value="97.3%" delta={1.4} />
        </div>
      </Host>
    </Frame>
  );
}

/* ============================================================
   table
   ============================================================ */
function TableW({ theme = "dark", agentId = "probe" }) {
  const a = byId(agentId);
  const rows = [
    ["Ada", "engineer", "2024-03-01"],
    ["Linus", "maintainer", "2023-11-12"],
    ["Grace", "architect", "2022-06-30"],
    ["Edsger", "researcher", "2021-09-04"],
  ];
  return (
    <Frame theme={theme} accent="mono" pad={36} style={{ "--accent": a.c }}>
      <SpecHead k='type: "table"' t="Table"
        d="A scrollable CSV. Sticky uppercase header on the canvas tone, hairline zebra rows, monospace numerics, and a mono footer counting shown / total rows." />
      <Host chromeless>
        <div className="w-table-wrap">
          <table className="w-table">
            <thead><tr><th>name</th><th>role</th><th>joined</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}><td>{r[0]}</td><td>{r[1]}</td><td className="num">{r[2]}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="w-table-foot">Showing 4 of 128 rows (head)</div>
      </Host>
    </Frame>
  );
}

/* ============================================================
   tool-calls
   ============================================================ */
function ToolCallsW({ theme = "dark", agentId = "forge" }) {
  const a = byId(agentId);
  return (
    <Frame theme={theme} accent="mono" pad={36} style={{ "--accent": a.c }}>
      <SpecHead k='type: "tool-calls"' t="Tool calls"
        d="A live log of agent tool invocations. Status dot runs amber → settles to the agent accent (done) or rose (error). Rows expand to mono argument / output JSON." />
      <Host title="Tool calls">
        <ul className="w-tools" style={{ listStyle: "none", margin: 0, padding: 0 }}>
          <li className="w-tool">
            <div className="w-tool-row">
              <span className="w-dot done" />
              <span className="t-name">search</span>
              <span className="t-args">· q: "vendor pricing"</span>
              <span className="t-toggle">hide</span>
            </div>
            <div className="t-body">
              <Note style={{ marginBottom: 4 }}>Arguments</Note>
              <pre>{`{ "q": "vendor pricing", "k": 8 }`}</pre>
              <Note style={{ margin: "8px 0 4px" }}>Output</Note>
              <pre>{`{ "hits": 8, "top": "pricing-2026.pdf" }`}</pre>
            </div>
          </li>
          <li className="w-tool">
            <div className="w-tool-row"><span className="w-dot running" /><span className="t-name">fetch_page</span><span className="t-args">· url: …/pricing</span><span className="t-toggle">show</span></div>
          </li>
          <li className="w-tool">
            <div className="w-tool-row"><span className="w-dot error" /><span className="t-name">parse_pdf</span><span className="t-args">· timeout</span><span className="t-toggle">show</span></div>
          </li>
        </ul>
      </Host>
    </Frame>
  );
}

/* ============================================================
   ai-chat-input
   ============================================================ */
function ChatInputW({ theme = "dark", agentId = "atlas" }) {
  const a = byId(agentId);
  const Composer = ({ text }) => (
    <div className="composer" style={text ? { borderColor: "var(--accent-line)" } : null}>
      {text ? <div className="ce" style={{ paddingBottom: 16 }}>{text}</div> : <div className="ph">Reply to {a.name}</div>}
      <div className="composer-row">
        <button className="cbtn"><Icons.attach s={17} /></button>
        <span className="spacer" />
        <button className="cbtn" style={{ minWidth: 34, padding: 0 }}><Icons.mic s={17} /></button>
        <button className={"send" + (text ? "" : " idle")}><Icons.arrowUp s={18} /></button>
      </div>
    </div>
  );
  return (
    <Frame theme={theme} accent="mono" pad={36} style={{ "--accent": a.c, "--accent-2": a.c, "--accent-line": `color-mix(in srgb, ${a.c} 44%, transparent)` }}>
      <SpecHead k='type: "ai-chat-input"' t="Chat input"
        d="The prototype composer, used verbatim: one quiet field, attach on the left, voice + send on the right. Send dims until there's text, then lights to the agent color; the border picks up the accent on focus." />
      <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 620 }}>
        <div>
          <Note style={{ marginBottom: 10 }}>Resting · empty</Note>
          <Composer />
        </div>
        <div>
          <Note style={{ marginBottom: 10 }}>Focused · with text</Note>
          <Composer text="Trace the checkout-service latency spike and tell me what to roll back" />
        </div>
      </div>
    </Frame>
  );
}

/* ============================================================
   ai-response
   ============================================================ */
function ResponseW({ theme = "dark", agentId = "atlas" }) {
  const a = byId(agentId);
  return (
    <Frame theme={theme} accent="mono" pad={36} style={{ "--accent": a.c, "--accent-2": a.c, "--accent-weak": `color-mix(in srgb, ${a.c} 16%, transparent)` }}>
      <SpecHead k='type: "ai-response"' t="Response transcript"
        d="The prototype transcript, used verbatim: user turns right in a bordered card; assistant turns lead with the avatar, name, accent tick, and timestamp — then prose, code, and copy / regenerate actions. The thinking state runs the liquid metaball under a shimmering status line." />
      <Host chromeless style={{ maxWidth: 600 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="msg user">
            <div className="msg-body" style={{ display: "flex", justifyContent: "flex-end" }}>
              <div className="ucard">Trace the p99 spike at 14:30 and tell me what to roll back.</div>
            </div>
          </div>
          <div className="msg assistant">
            <Glyph a={a} size={30} r={8} />
            <div className="msg-body">
              <div className="bubble-meta"><b>{a.name}</b><span className="hero-rule" style={{ width: 20, height: 2, margin: 0, background: a.c }} /><span className="t">9:14 AM</span></div>
              <p>The spike traces to one dependency. <b>payment-gateway</b> calls jumped to 880&nbsp;ms right after deploy <span className="mono" style={{ color: "var(--accent-2)" }}>b3f9c2</span>.</p>
              <div className="actions in"><span className="act"><Icons.copy s={15} /></span><span className="act"><Icons.refresh s={15} /></span></div>
            </div>
          </div>
          <div className="msg assistant">
            <Glyph a={a} size={30} r={8} cls="think" />
            <div className="msg-body">
              <div className="bubble-meta"><b>{a.name}</b><span className="hero-rule" style={{ width: 20, height: 2, margin: 0, background: a.c }} /><span className="t">9:14 AM</span></div>
              <div className="composing"><div className="goo"><span className="d1" /><span className="d2" /><span className="d3" /></div><div className="working shimmer">Correlating recent deploys…</div></div>
            </div>
          </div>
        </div>
      </Host>
    </Frame>
  );
}

/* ============================================================
/* ============================================================
   file-tree
   ============================================================ */
function FileTreeW({ theme = "dark", agentId = "forge" }) {
  const a = byId(agentId);
  const Node = ({ depth = 0, folder, open, name, size, sel }) => (
    <div className="w-node" style={{ paddingLeft: 8 + depth * 18, ...(sel ? { background: "var(--surface-2)", color: "var(--text)" } : null) }}>
      {folder ? <span className={"n-chev" + (open ? " open" : "")}><Icons.chevDown s={14} style={{ transform: "rotate(-90deg)" }} /></span> : <span style={{ width: 14 }} />}
      <span className="n-ic">{folder ? <Icons.folder s={15} /> : <Icons.doc s={15} />}</span>
      <span className="n-name">{name}</span>
      {size && <span className="n-size">{size}</span>}
      {!folder && <span className="n-actions"><span className="n-act"><Icons.pen s={13} /></span><span className="n-act"><Icons.dots s={13} /></span></span>}
    </div>
  );
  return (
    <Frame theme={theme} accent="mono" pad={36} style={{ "--accent": a.c }}>
      <SpecHead k='type: "file-tree"' t="File tree"
        d="Recursive folders with a rotating chevron. File rows reveal per-row actions on hover; byte sizes render in mono. Selection uses the neutral hover tone — not the accent — to stay quiet." />
      <Host style={{ maxWidth: 360 }}>
        <div className="w-tree">
          <Node folder open name="src" />
          <Node depth={1} name="index.ts" size="2.1 KB" />
          <Node depth={1} folder open name="widgets" />
          <Node depth={2} name="metrics.tsx" size="6.4 KB" sel />
          <Node depth={2} name="table.tsx" size="5.6 KB" />
          <Node folder name="docs" />
          <Node name="README.md" size="6.0 KB" />
        </div>
      </Host>
    </Frame>
  );
}

/* ============================================================
   markdown
   ============================================================ */
function MarkdownW({ theme = "dark", agentId = "probe" }) {
  const a = byId(agentId);
  return (
    <Frame theme={theme} accent="mono" pad={36} style={{ "--accent": a.c, "--accent-line": `color-mix(in srgb, ${a.c} 44%, transparent)` }}>
      <SpecHead k='type: "markdown"' t="Markdown"
        d="Safe rich text — headings in the editorial serif, body in muted grotesk, links underlined in the agent accent, code in the mono face on a surface chip." />
      <Host style={{ maxWidth: 560 }}>
        <div className="w-md">
          <h2>Quick start</h2>
          <p>Type a message below and hit <strong>send</strong>. The agent streams its reply into the transcript. See <a href="#">the docs</a> for the full schema.</p>
          <h3>Configure a widget</h3>
          <pre><code>{`widgets:
  - name: "stats"
    type: "metrics"
    columns: 4`}</code></pre>
          <ul><li>Everything visible is a <code>widget</code>.</li><li>No built-in chrome.</li></ul>
          <blockquote>Pipe a long-form answer through here to show it formatted.</blockquote>
        </div>
      </Host>
    </Frame>
  );
}

/* ============================================================
   form
   ============================================================ */
function FormW({ theme = "dark", agentId = "relay" }) {
  const a = byId(agentId);
  return (
    <Frame theme={theme} accent="mono" pad={36} style={{ "--accent": a.c, "--accent-line": `color-mix(in srgb, ${a.c} 44%, transparent)`, "--accent-2": a.c }}>
      <SpecHead k='type: "form"' t="Form"
        d="Schema-driven fields on the canvas tone so they read as inputs, not cards. Required markers and focus rings use the agent accent; the submit button is the only filled control." />
      <Host style={{ maxWidth: 560 }}>
        <div className="w-form" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <div className="w-field"><span className="f-label">Job name<span className="req">*</span></span><input className="w-input" defaultValue="weekly-rollup" /></div>
          <div className="w-field"><span className="f-label">Model</span><div className="w-select">Opus 4.7</div></div>
          <div className="w-field"><span className="f-label">Max steps</span><input className="w-input" defaultValue="10" /></div>
          <div className="w-field"><span className="f-label">Schedule</span><input className="w-input" placeholder="0 9 * * 1" /></div>
          <div className="w-field" style={{ gridColumn: "1 / -1" }}><span className="f-label">Instructions</span><div className="w-textarea" style={{ minHeight: 58, color: "var(--text-3)" }}>Summarize the week and post to #ops…</div></div>
          <label className="w-check on" style={{ gridColumn: "1 / -1" }}><span className="box"><Icons.check s={13} /></span> Dry run only</label>
        </div>
        <div className="w-form-foot">
          <button className="w-btn w-btn-default">Run job</button>
          <button className="w-btn w-btn-ghost">Reset</button>
          <span className="w-form-msg">Job queued.</span>
        </div>
      </Host>
    </Frame>
  );
}

Object.assign(window, {
  Host, ButtonGroupW, MetricsW, TableW, ToolCallsW,
  ChatInputW, ResponseW, FileTreeW, MarkdownW, FormW,
});
