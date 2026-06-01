/* reference.jsx — HexaUI static reference / spec components.
   Renders non-interactive specimens of the locked prototype direction,
   reusing the exact classNames from theme.css so the reference stays
   1:1 with the live product. Exports building blocks to window. */
const { HexLogo, Icons } = window;

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

const Glyph = ({ a, size = 24, r = 7, cls = "" }) => (
  <span className={"glyph" + (cls ? " " + cls : "")}
        style={{ width: size, height: size, borderRadius: r, background: a.c, fontSize: Math.round(size * .46) }}>{a.k}</span>
);

/* establishes theme vars + background inside an artboard */
const Frame = ({ theme = "dark", accent = "mono", agentVars, bg, pad = 0, children, style }) => {
  const vars = agentVars ? {
    ["--accent"]: agentVars, ["--accent-2"]: agentVars,
    ["--accent-line"]: `color-mix(in srgb, ${agentVars} 44%, transparent)`,
    ["--accent-weak"]: `color-mix(in srgb, ${agentVars} 16%, transparent)`,
  } : null;
  return (
    <div className="hexa" data-theme={theme} data-accent={accent}
         style={{ height: "100%", background: bg || "var(--bg)", padding: pad, ...vars, ...style }}>
      {children}
    </div>
  );
};

/* small caption used to annotate specimens */
const Note = ({ children, style }) => (
  <div className="mono" style={{ fontSize: 10.5, letterSpacing: ".06em", textTransform: "uppercase",
       color: "var(--text-3)", ...style }}>{children}</div>
);
const SpecHead = ({ k, t, d }) => (
  <div style={{ marginBottom: 22 }}>
    <Note style={{ marginBottom: 9 }}>{k}</Note>
    <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-.02em", color: "var(--text)" }}>{t}</div>
    {d && <div style={{ fontSize: 13.5, color: "var(--text-2)", marginTop: 6, maxWidth: 560, lineHeight: 1.5 }}>{d}</div>}
  </div>
);

/* ============================================================
   FULL SCREENS
   ============================================================ */
function StaticSidebar() {
  const recents = ["Q3 incident triage", "Vendor pricing brief", "CI cache refactor",
                   "Fleet health check", "Invoice reconciliation", "CRM ↔ billing sync"];
  return (
    <aside className="sb">
      <div className="sb-head">
        <div className="brand"><HexLogo s={22} /><b>Hexa</b><span className="v">UI</span></div>
        <span className="spacer" />
        <span className="icon-btn" style={{ width: 30, height: 30 }}><Icons.sidebar s={17} /></span>
      </div>
      <div className="sb-body">
        <div className="newchat"><span className="ic"><Icons.plus s={17} /></span> New session</div>
        <div className="nav">
          <div className="nav-item"><span className="ic"><Icons.search s={17} /></span> Search</div>
          <div className="nav-item"><span className="ic"><Icons.layers s={17} /></span> Agents</div>
          <div className="nav-item"><span className="ic"><Icons.folder s={17} /></span> Workspace</div>
        </div>
        <div className="sb-section">
          <span className="lbl">Recent</span>
          <div className="recents">
            {recents.map((r, i) => (
              <div key={i} className="recent" style={i === 1 ? { background: "var(--surface-2)", color: "var(--text)" } : null}>{r}</div>
            ))}
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

/* topbar agent trigger (the picker lives here, not in the composer) */
const AgentTrigger = ({ agent }) => (
  <div className="agent-pick">
    <Glyph a={agent} size={22} r={6} cls="live" />
    <span>{agent.name}</span>
    <span className="chev"><Icons.chevDown s={16} /></span>
  </div>
);

/* composer — note: NO agent selector in the input row (matches latest prototype) */
const StaticComposer = ({ placeholder, value, mini, focus }) => (
  <div className="composer" style={{ ...(mini ? { boxShadow: "none" } : null), ...(focus ? { borderColor: "var(--accent-line)" } : null) }}>
    {value
      ? <div className="ce" style={{ paddingBottom: 16 }}>{value}</div>
      : <div className="ph">{placeholder}</div>}
    <div className="composer-row">
      <button className="cbtn"><Icons.attach s={17} /></button>
      <span className="spacer" />
      <button className="cbtn" style={{ minWidth: 34, padding: 0 }}><Icons.mic s={17} /></button>
      <button className={"send" + (value ? "" : " idle")}><Icons.arrowUp s={18} /></button>
    </div>
  </div>
);

function LandingScreen({ theme = "dark", agentId = "probe" }) {
  const agent = byId(agentId);
  return (
    <Frame theme={theme} accent="mono" agentVars={agent.c} style={{ display: "flex" }}>
      <div className="hexa app" data-theme={theme} data-accent="mono"
           style={{ "--accent": agent.c, "--accent-2": agent.c,
                    "--accent-line": `color-mix(in srgb, ${agent.c} 44%, transparent)`,
                    "--accent-weak": `color-mix(in srgb, ${agent.c} 16%, transparent)`,
                    height: "100%", width: "100%" }}>
        <StaticSidebar />
        <div className="main">
          <div className="topbar">
            <AgentTrigger agent={agent} />
            <span className="spacer" />
            <span className="icon-btn"><Icons.history s={18} /></span>
            <span className="icon-btn"><Icons.dots s={18} /></span>
          </div>
          <div className="stage" style={{ alignItems: "stretch" }}>
            <div style={{ width: "100%", maxWidth: 720, margin: "0 auto" }}>
              <div style={{ marginBottom: 26 }}>
                <h1 className="greet" style={{ textAlign: "left", fontSize: "calc(var(--fs-greet) * 1.12)", margin: 0, lineHeight: 1.1 }}>
                  Good morning,<br />Mark
                </h1>
                <div className="hero-rule" />
                <div className="talking" style={{ margin: "16px 0 0" }}>
                  <span className="seg" /> Talking to <b>{agent.name}</b> · {agent.role}
                </div>
              </div>
              <StaticComposer placeholder="Ask Probe to research or retrieve" />
              <div className="chips" style={{ justifyContent: "flex-start" }}>
                {["Search the knowledge base", "Compare sources", "Extract from documents"].map((c, i) => (
                  <div key={i} className="chip">{c}</div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Frame>
  );
}

function ChatScreen({ theme = "dark", agentId = "atlas" }) {
  const agent = byId(agentId);
  return (
    <Frame theme={theme} accent="mono" style={{ display: "flex" }}>
      <div className="hexa app" data-theme={theme} data-accent="mono"
           style={{ "--accent": agent.c, "--accent-2": agent.c,
                    "--accent-line": `color-mix(in srgb, ${agent.c} 44%, transparent)`,
                    "--accent-weak": `color-mix(in srgb, ${agent.c} 16%, transparent)`,
                    height: "100%", width: "100%" }}>
        <StaticSidebar />
        <div className="main">
          <div className="topbar">
            <AgentTrigger agent={agent} />
            <span style={{ color: "var(--text-3)", fontSize: 14 }}>· Q3 incident triage</span>
            <span className="spacer" />
            <span className="icon-btn"><Icons.history s={18} /></span>
            <span className="icon-btn"><Icons.dots s={18} /></span>
          </div>
          <div className="thread">
            <div className="thread-inner">
              <div className="msg user">
                <div className="msg-body" style={{ display: "flex", justifyContent: "flex-end" }}>
                  <div className="ucard">checkout-service p99 latency spiked at 14:30. Trace it and tell me what to roll back.</div>
                </div>
              </div>
              <div className="msg assistant">
                <Glyph a={agent} size={30} r={8} />
                <div className="msg-body">
                  <div className="bubble-meta"><b>{agent.name}</b>
                    <span className="hero-rule" style={{ width: 20, height: 2, margin: 0, background: agent.c }} />
                    <span className="t">9:14 AM</span></div>
                  <p>The spike traces to one dependency. <b>payment-gateway</b> calls jumped from a 40&nbsp;ms median to 880&nbsp;ms right after deploy <span className="mono" style={{ color: "var(--accent-2)" }}>b3f9c2</span> — it added a synchronous fraud-check hop with no timeout.</p>
                  <CodeSpec />
                  <p>I can apply this now, or hand off to <b>Sentry</b> to watch p99 recover before closing the incident.</p>
                  <div className="actions in">
                    <span className="act"><Icons.copy s={15} /></span>
                    <span className="act"><Icons.refresh s={15} /></span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div className="thread-foot">
            <StaticComposer mini placeholder="Reply to Atlas" />
          </div>
        </div>
      </div>
    </Frame>
  );
}

/* ============================================================
   FOUNDATIONS
   ============================================================ */
const DARK_SCALE = [
  ["--bg", "#1e1e1f", "Canvas"],
  ["--bg-2", "#181819", "Sidebar / code"],
  ["--surface", "#282829", "Input · cards"],
  ["--surface-2", "#323234", "Hover"],
  ["--surface-3", "#3d3d40", "Pressed"],
  ["--text", "#ecedef", "Primary text"],
  ["--text-2", "#a3a6ac", "Secondary"],
  ["--text-3", "#6e7177", "Tertiary / icons"],
];
const LIGHT_SCALE = [
  ["--bg", "#ffffff", "Canvas"],
  ["--bg-2", "#f5f6f7", "Sidebar / code"],
  ["--surface", "#ffffff", "Input · cards"],
  ["--surface-2", "#f0f1f3", "Hover"],
  ["--surface-3", "#e7e9ec", "Pressed"],
  ["--text", "#191c21", "Primary text"],
  ["--text-2", "#5c616a", "Secondary"],
  ["--text-3", "#969ba3", "Tertiary / icons"],
];

function ColorScale({ theme }) {
  const scale = theme === "light" ? LIGHT_SCALE : DARK_SCALE;
  return (
    <Frame theme={theme} pad={40}>
      <SpecHead k={theme === "light" ? "Color · Light" : "Color · Dark"} t="Warm-neutral scale"
        d="A single greyscale carries the whole UI — text, surfaces, and lines all read from these eight tokens. No decorative color in the chrome." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
        {scale.map(([tok, hex, use]) => (
          <div key={tok} style={{ border: "1px solid var(--line)", borderRadius: "var(--r-md)", overflow: "hidden", background: "var(--surface)" }}>
            <div style={{ height: 64, background: hex, borderBottom: "1px solid var(--line-2)" }} />
            <div style={{ padding: "10px 12px" }}>
              <div className="mono" style={{ fontSize: 11.5, color: "var(--text)" }}>{tok}</div>
              <div className="mono" style={{ fontSize: 10.5, color: "var(--text-3)", marginTop: 2 }}>{hex}</div>
              <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 7 }}>{use}</div>
            </div>
          </div>
        ))}
      </div>
    </Frame>
  );
}

function AgentRoster({ theme = "dark" }) {
  return (
    <Frame theme={theme} pad={40}>
      <SpecHead k="Color · Accent" t="The agent is the accent"
        d="Chrome stays monochrome; the only color in the product is the active agent's signature hue. It tints the avatar, the send button, links, the hero rule, and focus states. Six agents, six fixed colors." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
        {AGENTS.map((a) => (
          <div key={a.id} style={{ display: "flex", alignItems: "center", gap: 13, border: "1px solid var(--line)",
               borderRadius: "var(--r-md)", padding: "13px 15px", background: "var(--surface)" }}>
            <Glyph a={a} size={38} r={10} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14.5, fontWeight: 600, color: "var(--text)" }}>{a.name}</div>
              <div style={{ fontSize: 12, color: "var(--text-2)" }}>{a.role}</div>
              <div className="mono" style={{ fontSize: 10.5, color: "var(--text-3)", marginTop: 4 }}>{a.c} · {a.fw}</div>
            </div>
          </div>
        ))}
      </div>
    </Frame>
  );
}

function TypeSpecimen({ theme = "dark" }) {
  return (
    <Frame theme={theme} pad={40}>
      <SpecHead k="Type" t="Quiet grotesk, editorial serif"
        d="Hanken Grotesk runs the interface. A transitional serif (Source Serif / Baskerville) is reserved for the greeting and long-form answers. IBM Plex Mono labels metadata, code, and identifiers." />
      <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
        <div>
          <Note style={{ marginBottom: 10 }}>Hero · serif · 47px</Note>
          <div className="greet" style={{ fontSize: 47, margin: 0, fontFamily: "var(--font-serif)", fontWeight: 400, letterSpacing: "-.01em" }}>Good morning, Mark</div>
        </div>
        <hr className="hr" />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 30 }}>
          <div>
            <Note style={{ marginBottom: 10 }}>UI sans · Hanken Grotesk</Note>
            <div style={{ fontSize: 22, fontWeight: 600, color: "var(--text)", letterSpacing: "-.01em" }}>Semibold 22 — section</div>
            <div style={{ fontSize: 15, color: "var(--text)", marginTop: 8 }}>Regular 15 — body / input</div>
            <div style={{ fontSize: 13.5, color: "var(--text-2)", marginTop: 8 }}>Regular 13.5 — secondary</div>
            <div className="lbl" style={{ marginTop: 12 }}>Label · 11.5 · uppercase</div>
          </div>
          <div>
            <Note style={{ marginBottom: 10 }}>Serif prose · answers</Note>
            <p style={{ fontFamily: "var(--font-serif)", fontSize: 16.5, lineHeight: 1.66, color: "var(--text)", margin: 0 }}>
              Across the leading vendors, pricing splits along one axis: seats versus runs.
            </p>
            <Note style={{ margin: "16px 0 8px" }}>Mono · IBM Plex</Note>
            <div className="mono" style={{ fontSize: 13, color: "var(--text-2)" }}>rollback.yaml · b3f9c2 · 880&nbsp;ms</div>
          </div>
        </div>
      </div>
    </Frame>
  );
}

function TokensSpec({ theme = "dark" }) {
  const radii = [["--r-sm", 7], ["--r-md", 11], ["--r-lg", 16], ["--r-pill", 999]];
  return (
    <Frame theme={theme} pad={40}>
      <SpecHead k="Form" t="Radii, spacing & elevation"
        d="Soft but restrained corners. One shadow token lifts the composer and menus off the canvas; everything else sits flat, separated by hairlines." />
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 28 }}>
        {radii.map(([tok, px]) => (
          <div key={tok} style={{ textAlign: "center" }}>
            <div style={{ width: 84, height: 64, background: "var(--surface)", border: "1px solid var(--line)",
                 borderRadius: px === 999 ? 999 : px }} />
            <div className="mono" style={{ fontSize: 10.5, color: "var(--text)", marginTop: 8 }}>{tok}</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--text-3)" }}>{px === 999 ? "pill" : px + "px"}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        <div>
          <Note style={{ marginBottom: 10 }}>Hairlines</Note>
          <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "var(--r-md)", padding: 16 }}>
            <div style={{ fontSize: 12.5, color: "var(--text-2)" }}>--line · 10% white</div>
            <hr className="hr" style={{ margin: "12px 0" }} />
            <div style={{ fontSize: 12.5, color: "var(--text-2)" }}>--line-2 · 5.5% white</div>
            <hr className="dashrule" style={{ margin: "12px 0" }} />
            <div style={{ fontSize: 12.5, color: "var(--text-2)" }}>dashrule · technical divider</div>
          </div>
        </div>
        <div>
          <Note style={{ marginBottom: 10 }}>Elevation · --shadow</Note>
          <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "var(--r-lg)",
               padding: 16, boxShadow: "var(--shadow)" }}>
            <div style={{ fontSize: 12.5, color: "var(--text-2)", lineHeight: 1.6 }}>Used only on the composer and floating menus. 0 1px 2px + 0 12px 34px.</div>
          </div>
        </div>
      </div>
    </Frame>
  );
}

/* ============================================================
   COMPONENTS
   ============================================================ */
const CodeSpec = () => (
  <div className="codeblk">
    <div className="cb-head"><Icons.doc s={14} /><span className="lbl">rollback.yaml</span></div>
    <pre>
      <div><span className="k">target</span>: <span className="s">checkout-service</span></div>
      <div><span className="k">action</span>: <span className="s">rollback</span></div>
      <div><span className="k">to_revision</span>: <span className="s">"a17d04"</span></div>
      <div><span className="k">drain</span>: <span className="s">30s</span></div>
    </pre>
  </div>
);

function ComposerSpec({ theme = "dark" }) {
  const agent = byId("probe");
  return (
    <Frame theme={theme} accent="mono" pad={40}
           style={{ "--accent": agent.c, "--accent-2": agent.c, "--accent-line": `color-mix(in srgb, ${agent.c} 44%, transparent)` }}>
      <SpecHead k="Component · Composer" t="Input"
        d="One quiet field. Attach on the left, voice + send on the right — the agent selector lives in the top bar, not here. Send dims until there's text, then lights to the agent color. Border picks up the accent on focus." />
      <div style={{ display: "flex", flexDirection: "column", gap: 22, maxWidth: 620 }}>
        <div>
          <Note style={{ marginBottom: 10 }}>Resting · empty</Note>
          <StaticComposer placeholder="Ask Probe to research or retrieve" />
        </div>
        <div>
          <Note style={{ marginBottom: 10 }}>Focused · with text</Note>
          <StaticComposer focus value="Compare how the three leading vendors price their agent platforms" />
        </div>
      </div>
    </Frame>
  );
}

function ChipsButtonsSpec({ theme = "dark" }) {
  const agent = byId("atlas");
  return (
    <Frame theme={theme} accent="mono" pad={40}
           style={{ "--accent": agent.c, "--accent-2": agent.c, "--accent-weak": `color-mix(in srgb, ${agent.c} 16%, transparent)` }}>
      <SpecHead k="Component · Controls" t="Chips, buttons & icon actions"
        d="Suggestion chips seed an empty session. Buttons stay ghost-quiet; only the send action carries the accent fill." />
      <Note style={{ marginBottom: 10 }}>Suggestion chips</Note>
      <div className="chips" style={{ justifyContent: "flex-start", marginTop: 0, marginBottom: 26 }}>
        {["Trace a run", "Summarize a doc", "Draft an automation"].map((c, i) => <div key={i} className="chip">{c}</div>)}
      </div>
      <Note style={{ marginBottom: 12 }}>Buttons & icon actions</Note>
      <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <button className="send"><Icons.arrowUp s={18} /></button>
        <button className="send idle"><Icons.arrowUp s={18} /></button>
        <button className="cbtn outline"><Icons.attach s={16} /> Attach</button>
        <span className="icon-btn"><Icons.history s={18} /></span>
        <span className="icon-btn"><Icons.sidebar s={18} /></span>
        <span className="icon-btn"><Icons.dots s={18} /></span>
        <div className="act"><Icons.copy s={15} /></div>
        <div className="act"><Icons.refresh s={15} /></div>
      </div>
      <div style={{ display: "flex", gap: 28, marginTop: 26, flexWrap: "wrap" }}>
        {[16, 22, 30, 38].map((s) => (
          <div key={s} style={{ textAlign: "center" }}>
            <Glyph a={agent} size={s} r={Math.round(s / 4.4)} cls="live" />
            <div className="mono" style={{ fontSize: 10, color: "var(--text-3)", marginTop: 8 }}>{s}px</div>
          </div>
        ))}
        <div style={{ alignSelf: "center" }}><Note>Agent avatars · sizes</Note></div>
      </div>
    </Frame>
  );
}

function MenuSpec({ theme = "dark" }) {
  return (
    <Frame theme={theme} accent="mono" pad={40}
           style={{ "--accent": "#3f9d94", "--accent-weak": "color-mix(in srgb, #3f9d94 16%, transparent)" }}>
      <SpecHead k="Component · Menu" t="Agent picker"
        d="Opened from the top bar. Searchable roster; the active agent is marked and tinted with its own color." />
      <div style={{ position: "relative", height: 360 }}>
        <div className="menu" style={{ width: 320, position: "static", boxShadow: "var(--shadow)" }}>
          <div className="menu-search"><Icons.search s={15} /> Search agents</div>
          <div className="menu-list">
            {AGENTS.map((a) => (
              <div key={a.id} className={"menu-row" + (a.id === "probe" ? " sel" : "")}>
                <Glyph a={a} size={30} r={8} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <b style={{ fontSize: 13.5 }}>{a.name}</b>
                  <div className="role">{a.role} · {a.fw}</div>
                </div>
                {a.id === "probe" && <span style={{ color: "var(--accent)" }}><Icons.check s={16} /></span>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </Frame>
  );
}

function MessagesSpec({ theme = "dark" }) {
  const agent = byId("atlas");
  return (
    <Frame theme={theme} accent="mono" pad={40}
           style={{ "--accent": agent.c, "--accent-2": agent.c }}>
      <SpecHead k="Component · Conversation" t="Messages"
        d="User turns sit right in a bordered card. Agent turns lead with the avatar, name, an accent tick, and timestamp. Answers can carry code blocks and copy / regenerate actions." />
      <div style={{ maxWidth: 640 }}>
        <div className="msg user" style={{ marginBottom: 26 }}>
          <div className="msg-body" style={{ display: "flex", justifyContent: "flex-end" }}>
            <div className="ucard">checkout-service p99 latency spiked at 14:30. Trace it.</div>
          </div>
        </div>
        <div className="msg assistant">
          <Glyph a={agent} size={30} r={8} />
          <div className="msg-body">
            <div className="bubble-meta"><b>{agent.name}</b>
              <span className="hero-rule" style={{ width: 20, height: 2, margin: 0, background: agent.c }} />
              <span className="t">9:14 AM</span></div>
            <p>The spike traces to one dependency. <b>payment-gateway</b> calls jumped to 880&nbsp;ms right after deploy <span className="mono" style={{ color: "var(--accent-2)" }}>b3f9c2</span>.</p>
            <CodeSpec />
            <div className="actions in">
              <span className="act"><Icons.copy s={15} /></span>
              <span className="act"><Icons.refresh s={15} /></span>
            </div>
          </div>
        </div>
      </div>
    </Frame>
  );
}

function StatesSpec({ theme = "dark" }) {
  const agent = byId("atlas");
  return (
    <Frame theme={theme} accent="mono" pad={40}
           style={{ "--accent": agent.c, "--accent-2": agent.c,
                    "--accent-weak": `color-mix(in srgb, ${agent.c} 16%, transparent)` }}>
      <SpecHead k="Component · Agent state" t="Thinking & streaming"
        d="While the agent works, a liquid metaball loader runs under a shimmering status line. As it answers, a block caret in the agent color trails the streamed text." />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 30, maxWidth: 680 }}>
        <div>
          <Note style={{ marginBottom: 12 }}>Thinking / composing</Note>
          <div className="msg assistant">
            <Glyph a={agent} size={30} r={8} cls="think" />
            <div className="msg-body">
              <div className="bubble-meta"><b>{agent.name}</b>
                <span className="hero-rule" style={{ width: 20, height: 2, margin: 0, background: agent.c }} />
                <span className="t">9:14 AM</span></div>
              <div className="composing">
                <div className="goo"><span className="d1" /><span className="d2" /><span className="d3" /></div>
                <div className="working shimmer">Correlating recent deploys…</div>
              </div>
            </div>
          </div>
        </div>
        <div>
          <Note style={{ marginBottom: 12 }}>Streaming answer</Note>
          <div className="msg assistant">
            <Glyph a={agent} size={30} r={8} />
            <div className="msg-body">
              <div className="bubble-meta"><b>{agent.name}</b>
                <span className="hero-rule" style={{ width: 20, height: 2, margin: 0, background: agent.c }} />
                <span className="t">9:14 AM</span></div>
              <p>The spike traces to one dependency. <b>payment-gateway</b> calls jumped<span className="caret" /></p>
            </div>
          </div>
        </div>
      </div>
      <Note style={{ margin: "30px 0 12px" }}>Avatar presence — idle breathes, thinking pulses</Note>
      <div style={{ display: "flex", gap: 40, alignItems: "center" }}>
        <div style={{ textAlign: "center" }}><Glyph a={agent} size={34} r={9} cls="live" /><div className="mono" style={{ fontSize: 10, color: "var(--text-3)", marginTop: 10 }}>idle</div></div>
        <div style={{ textAlign: "center" }}><Glyph a={agent} size={34} r={9} cls="think" /><div className="mono" style={{ fontSize: 10, color: "var(--text-3)", marginTop: 10 }}>thinking</div></div>
      </div>
    </Frame>
  );
}

Object.assign(window, {
  AGENTS, byId, Glyph, Frame, Note, SpecHead,
  LandingScreen, ChatScreen,
  ColorScale, AgentRoster, TypeSpecimen, TokensSpec,
  ComposerSpec, ChipsButtonsSpec, MenuSpec, MessagesSpec, StatesSpec,
});
