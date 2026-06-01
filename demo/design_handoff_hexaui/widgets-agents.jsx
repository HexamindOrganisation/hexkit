/* widgets-agents.jsx — how the widget UI shifts when you switch agents.
   Two mechanisms:
     1. RECOLOR — page.main_color = the agent's signature color, so every
        accent (buttons, focus, deltas, tool dots, links) re-tints at once.
     2. RECOMPOSE — each agent ships its own YAML, so the widget SET and
        layout differ: Forge is code-shaped, Ledger is numbers-shaped, etc.
   Pulls shared helpers from window (reference.jsx + widgets.jsx). */
const { Icons, Glyph, AGENTS, byId, Frame, Note, SpecHead } = window;

const agentVars = (a) => ({
  "--accent": a.c, "--accent-2": a.c,
  "--accent-line": `color-mix(in srgb, ${a.c} 44%, transparent)`,
  "--accent-weak": `color-mix(in srgb, ${a.c} 16%, transparent)`,
});

/* ---------- compact widget renderers (raw HexaUI classes) ---------- */
const MHeader = ({ a, title, sub }) => (
  <div className="w-pageheader" style={{ marginBottom: 18 }}>
    <Glyph a={a} size={36} r={10} cls="live" />
    <div>
      <div className="ph-title" style={{ fontSize: 19 }}>{title}</div>
      <div className="ph-sub">{sub}</div>
      <div className="ph-tick" />
    </div>
    <span className="spacer" style={{ flex: 1 }} />
    <button className="w-btn w-btn-default sm">New run</button>
    <button className="w-btn w-btn-outline sm">Settings</button>
  </div>
);
const MMetric = ({ label, value, delta, hint }) => (
  <div className="w-metric">
    <div className="m-label">{label}</div>
    <div className="m-row"><div className="m-value" style={{ fontSize: 22 }}>{value}</div>
      {delta != null && <span className={"w-delta " + (delta > 0 ? "up" : "down")}>{delta > 0 ? "▲" : "▼"} {Math.abs(delta)}</span>}</div>
    {hint && <div className="m-hint">{hint}</div>}
  </div>
);
const MChat = ({ ph }) => (
  <div className="w-chatinput" style={{ boxShadow: "none" }}>
    <div className="ta ph">{ph}</div>
    <div className="ci-btns"><button className="w-ci-send"><Icons.arrowUp s={18} /></button></div>
  </div>
);
const MNode = ({ d = 0, folder, open, name, size, sel }) => (
  <div className="w-node" style={{ paddingLeft: 6 + d * 16, height: 28, ...(sel ? { background: "var(--surface-2)", color: "var(--text)" } : null) }}>
    {folder ? <span className={"n-chev" + (open ? " open" : "")}><Icons.chevDown s={13} style={{ transform: "rotate(-90deg)" }} /></span> : <span style={{ width: 13 }} />}
    <span className="n-ic">{folder ? <Icons.folder s={14} /> : <Icons.doc s={14} />}</span>
    <span className="n-name">{name}</span>{size && <span className="n-size">{size}</span>}
  </div>
);
const MTool = ({ s, name, args }) => (
  <li className="w-tool"><div className="w-tool-row" style={{ padding: "7px 10px" }}><span className={"w-dot " + s} /><span className="t-name">{name}</span><span className="t-args">{args}</span></div></li>
);

/* ============================================================
   1 · ACCENT — the agent IS the accent
   ============================================================ */
function AccentStrip({ theme = "dark" }) {
  const show = ["atlas", "probe", "forge", "sentry", "ledger", "relay"].map(byId);
  return (
    <Frame theme={theme} accent="mono" pad={40}>
      <SpecHead k="Switching · 1" t="The agent is the accent"
        d="Set page.main_color to the active agent's hue and every widget re-tints from one variable — no per-widget overrides. Below: the same primary button, send, a positive delta, and a running tool dot, rendered under all six agents." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
        {show.map((a) => (
          <div key={a.id} style={{ ...agentVars(a), border: "1px solid var(--line)", borderRadius: "var(--r-md)", background: "var(--surface)", padding: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 13 }}>
              <Glyph a={a} size={22} r={6} />
              <span style={{ fontSize: 13.5, fontWeight: 600, color: "var(--text)" }}>{a.name}</span>
              <span className="mono" style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-3)" }}>{a.c}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <button className="w-btn w-btn-default sm">Run</button>
              <button className="w-ci-send" style={{ width: 30, height: 30 }}><Icons.arrowUp s={16} /></button>
              <span className="w-delta up">▲ 1.4</span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, marginLeft: "auto" }}>
                <span className="w-dot done" /><span className="mono" style={{ fontSize: 11, color: "var(--text-3)" }}>done</span>
              </span>
            </div>
          </div>
        ))}
      </div>
      <div className="mono" style={{ fontSize: 11.5, color: "var(--text-2)", marginTop: 20, background: "var(--bg-2)", border: "1px solid var(--line-2)", borderRadius: "var(--r-sm)", padding: "12px 14px", lineHeight: 1.7 }}>
        <span style={{ color: "var(--text-3)" }}>page:</span><br />
        &nbsp;&nbsp;layout_type: <span style={{ color: "var(--accent-2)" }}>"grid"</span><br />
        &nbsp;&nbsp;main_color: <span style={{ color: "var(--accent-2)" }}>"{byId("probe").c}"</span> <span style={{ color: "var(--text-3)" }}># ← swap per agent to recolor the whole page</span>
      </div>
    </Frame>
  );
}

/* ============================================================
   2 · RECOMPOSE — each agent ships its own widget set
   ============================================================ */
function ForgeDash({ theme = "dark" }) {
  const a = byId("forge");
  return (
    <Frame theme={theme} accent="mono" pad={32} style={agentVars(a)}>
      <MHeader a={a} title="Forge" sub="Code & build · OpenAI Agents" />
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,5fr) minmax(0,7fr)", gap: 16 }}>
        <div className="w-host"><div className="w-head"><span className="lbl">Repository</span></div>
          <div className="w-tree">
            <MNode folder open name="src" /><MNode d={1} name="index.ts" size="2.1 KB" />
            <MNode d={1} folder open name="ci" /><MNode d={2} name="build.yaml" size="1.2 KB" sel /><MNode d={2} name="test.yaml" size="0.8 KB" />
            <MNode name="README.md" size="6.0 KB" />
          </div>
        </div>
        <div className="w-host"><div className="w-head"><span className="lbl">Tool calls</span></div>
          <ul className="w-tools" style={{ listStyle: "none", margin: 0, padding: 0 }}>
            <MTool s="done" name="read_file" args="· ci/build.yaml" />
            <MTool s="done" name="edit_file" args="· cache.key" />
            <MTool s="running" name="run_ci" args="· dry-run" />
          </ul>
        </div>
      </div>
      <div style={{ marginTop: 16 }}><MChat ph="Tell Forge what to build" /></div>
    </Frame>
  );
}

function LedgerDash({ theme = "dark" }) {
  const a = byId("ledger");
  const rows = [["INV-2041", "Northwind", "$12,400", "ok"], ["INV-2042", "Acme", "$3,180", "flag"], ["INV-2043", "Globex", "$8,650", "ok"], ["INV-2044", "Initech", "$1,920", "flag"]];
  return (
    <Frame theme={theme} accent="mono" pad={32} style={agentVars(a)}>
      <MHeader a={a} title="Ledger" sub="Finance operations · CrewAI" />
      <div className="w-metrics" style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 16 }}>
        <MMetric label="Batch total" value="$26.1K" hint="this week" />
        <MMetric label="Matched" value="94%" delta={2} />
        <MMetric label="Flagged" value="2" delta={-1} />
        <MMetric label="Avg variance" value="$640" />
      </div>
      <div className="w-host"><div className="w-head"><span className="lbl">Invoice reconciliation</span></div>
        <div className="w-table-wrap">
          <table className="w-table"><thead><tr><th>invoice</th><th>vendor</th><th>amount</th><th>status</th></tr></thead>
            <tbody>{rows.map((r, i) => (
              <tr key={i}><td className="num">{r[0]}</td><td>{r[1]}</td><td className="num">{r[2]}</td>
                <td><span style={{ color: r[3] === "flag" ? "var(--danger)" : "var(--ok)", fontWeight: 600, fontSize: 12 }}>{r[3] === "flag" ? "● flag" : "● ok"}</span></td></tr>
            ))}</tbody></table>
        </div>
      </div>
      <div style={{ marginTop: 16 }}><MChat ph="Ask Ledger about finance ops" /></div>
    </Frame>
  );
}

function ProbeDash({ theme = "dark" }) {
  const a = byId("probe");
  return (
    <Frame theme={theme} accent="mono" pad={32} style={agentVars(a)}>
      <MHeader a={a} title="Probe" sub="Research & retrieval · LlamaIndex" />
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,3fr) minmax(0,5fr) minmax(0,4fr)", gap: 16 }}>
        <div className="w-host"><div className="w-head"><span className="lbl">History</span></div>
          <div className="w-history">
            <div className="w-convo active"><div className="c-title">Vendor pricing</div><div className="c-prev">3 sources compared</div></div>
            <div className="w-convo"><div className="c-title">Compliance scan</div><div className="c-prev">SOC2 review</div></div>
          </div>
        </div>
        <div className="w-host chromeless">
          <div className="w-resp">
            <div className="msg user" style={{ margin: 0 }}><div className="msg-body" style={{ display: "flex", justifyContent: "flex-end" }}><div className="ucard">Compare the three vendors' pricing.</div></div></div>
            <div className="abubble">Pricing splits on one axis: <b style={{ fontFamily: "var(--font-sans)" }}>seats vs. runs</b>. Two anchor to per-seat; the third bills per execution.</div>
            <div className="abubble partial">Pulling the pricing pages<span className="caret" /></div>
          </div>
        </div>
        <div className="w-host"><div className="w-head"><span className="lbl">Sources</span></div>
          <div className="w-md" style={{ fontSize: 13 }}>
            <ul style={{ paddingLeft: 18 }}>
              <li><a href="#">pricing-2026.pdf</a></li>
              <li><a href="#">vendor-b-tiers.md</a></li>
              <li><a href="#">rfp-notes.txt</a></li>
            </ul>
            <blockquote style={{ fontSize: 12.5 }}>Per-seat stays cheaper for wide, low-volume rollouts.</blockquote>
          </div>
        </div>
      </div>
      <div style={{ marginTop: 16 }}><MChat ph="Ask Probe to research or retrieve" /></div>
    </Frame>
  );
}

/* ============================================================
   3 · TRANSITION — what the switch itself feels like
   ============================================================ */
function SwitchNotes({ theme = "dark" }) {
  const from = byId("probe"), to = byId("atlas");
  const rows = [
    ["Accent bloom", "A soft blur of the new color blooms behind the avatar as it settles in (≈0.6s) — the recolor reads as a deliberate handoff, not a flash."],
    ["Avatar settle", "The agent glyph scales up from 0.82 and breathes a faint ring in its own color while idle, pulsing harder while thinking."],
    ["Identity swap", "page-header glyph, title sub-line, and accent tick all adopt the new agent — the page announces who you're talking to."],
    ["Seeded intent", "Empty-state chips, the chat placeholder, and the default widget set change per agent (Forge → code, Ledger → numbers)."],
    ["Thinking color", "The composing metaball, status shimmer, and streaming caret all render in the agent accent, so even the loading state is on-brand."],
  ];
  return (
    <Frame theme={theme} accent="mono" pad={40}>
      <SpecHead k="Switching · 3" t="What the handoff feels like"
        d="The recolor is instant under the hood (one CSS variable), but a few transform-only motions make the switch legible and calm." />
      <div style={{ display: "flex", alignItems: "center", gap: 22, marginBottom: 26 }}>
        <div style={{ ...agentVars(from), textAlign: "center" }}>
          <span className="ava-wrap" style={{ display: "inline-flex", position: "relative" }}><Glyph a={from} size={46} r={13} cls="live" /></span>
          <div style={{ fontSize: 12.5, color: "var(--text-2)", marginTop: 10 }}>{from.name}</div>
        </div>
        <span style={{ color: "var(--text-3)" }}><Icons.arrowUp s={20} style={{ transform: "rotate(90deg)" }} /></span>
        <div style={{ ...agentVars(to), textAlign: "center", position: "relative" }}>
          <span className="ava-wrap" style={{ display: "inline-flex", position: "relative" }}><span className="bloom" /><Glyph a={to} size={46} r={13} cls="think" /></span>
          <div style={{ fontSize: 12.5, color: "var(--text-2)", marginTop: 10 }}>{to.name}</div>
        </div>
        <div style={{ flex: 1, paddingLeft: 14, borderLeft: "1px solid var(--line-2)" }}>
          <Note style={{ marginBottom: 6 }}>The only color in the product</Note>
          <div style={{ fontSize: 13.5, color: "var(--text-2)", lineHeight: 1.55, maxWidth: 360 }}>Chrome stays monochrome end-to-end; the agent's hue is the single signal that tells you which mind is on the other end.</div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {rows.map(([t, d], i) => (
          <div key={i} style={{ border: "1px solid var(--line)", borderRadius: "var(--r-md)", background: "var(--surface)", padding: "13px 15px" }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--text)", marginBottom: 5 }}>{t}</div>
            <div style={{ fontSize: 12.5, color: "var(--text-2)", lineHeight: 1.55 }}>{d}</div>
          </div>
        ))}
      </div>
    </Frame>
  );
}

Object.assign(window, { AccentStrip, ForgeDash, LedgerDash, ProbeDash, SwitchNotes });
