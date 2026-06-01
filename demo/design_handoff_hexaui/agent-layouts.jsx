/* agent-layouts.jsx — showcase of full app layouts, one per agent.
   Each is a believable product configuration a developer would author in
   YAML: a constant chrome shell (side menu = conversation history + file
   tree + agent identity) wrapping an agent-specific arrangement of MAIN
   widgets. ai-response and ai-chat-input use the prototype design verbatim.
   Pulls shared helpers from window. */
const { Icons, Glyph, HexLogo, AGENTS, byId, Frame, Note } = window;

const agentVars = (a) => ({
  "--accent": a.c, "--accent-2": a.c,
  "--accent-line": `color-mix(in srgb, ${a.c} 44%, transparent)`,
  "--accent-weak": `color-mix(in srgb, ${a.c} 16%, transparent)`,
});

/* ---------- CHROME (constant side menu + top bar + composer) ---------- */
function TreeNode({ d = 0, folder, open, name, size, sel }) {
  return (
    <div className="w-node" style={{ paddingLeft: 6 + d * 15, height: 28, ...(sel ? { background: "var(--surface-2)", color: "var(--text)" } : null) }}>
      {folder ? <span className={"n-chev" + (open ? " open" : "")}><Icons.chevDown s={13} style={{ transform: "rotate(-90deg)" }} /></span> : <span style={{ width: 13 }} />}
      <span className="n-ic">{folder ? <Icons.folder s={14} /> : <Icons.doc s={14} />}</span>
      <span className="n-name">{name}</span>{size && <span className="n-size">{size}</span>}
    </div>
  );
}

function SideMenu({ history, activeHist = 0, filesLabel, files }) {
  return (
    <aside className="sb" style={{ width: 270, flex: "0 0 270px" }}>
      <div className="sb-head">
        <div className="brand"><HexLogo s={22} /><b>Hexa</b><span className="v">UI</span></div>
        <span className="spacer" />
        <span className="icon-btn" style={{ width: 30, height: 30 }}><Icons.sidebar s={17} /></span>
      </div>
      <div className="sb-body">
        <div className="newchat"><span className="ic"><Icons.plus s={17} /></span> New session</div>
        <div className="sb-section">
          <span className="lbl">Conversation history</span>
          <div className="recents">
            {history.map((h, i) => (
              <div key={i} className="recent" style={i === activeHist ? { background: "var(--surface-2)", color: "var(--text)" } : null}>{h}</div>
            ))}
          </div>
        </div>
        <div className="sb-section">
          <span className="lbl">{filesLabel}</span>
          <div className="w-tree" style={{ marginTop: 2 }}>
            {files.map((f, i) => <TreeNode key={i} {...f} />)}
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

const TopBar = ({ agent, title }) => (
  <div className="topbar">
    <div className="agent-pick">
      <span className="ava-wrap" style={{ position: "relative", display: "inline-flex" }}><Glyph a={agent} size={22} r={6} cls="live" /></span>
      <span>{agent.name}</span><span className="chev"><Icons.chevDown s={16} /></span>
    </div>
    <span style={{ color: "var(--text-3)", fontSize: 14 }}>· {title}</span>
    <span className="spacer" />
    <span className="icon-btn"><Icons.history s={18} /></span>
    <span className="icon-btn"><Icons.dots s={18} /></span>
  </div>
);

const Composer = ({ ph, text }) => (
  <div className="composer">
    {text ? <div className="ce" style={{ paddingBottom: 16 }}>{text}</div> : <div className="ph">{ph}</div>}
    <div className="composer-row">
      <button className="cbtn"><Icons.attach s={17} /></button>
      <span className="spacer" />
      <button className="cbtn" style={{ minWidth: 34, padding: 0 }}><Icons.mic s={17} /></button>
      <button className={"send" + (text ? "" : " idle")}><Icons.arrowUp s={18} /></button>
    </div>
  </div>
);

function Shell({ agent, theme, title, history, activeHist, filesLabel, files, composerPh, children }) {
  return (
    <div className="hexa app" data-theme={theme} data-accent="mono" style={{ ...agentVars(agent), height: "100%", width: "100%" }}>
      <SideMenu history={history} activeHist={activeHist} filesLabel={filesLabel} files={files} />
      <div className="main">
        <TopBar agent={agent} title={title} />
        <div style={{ flex: 1, minHeight: 0, overflow: "hidden", padding: "18px 22px", display: "flex", flexDirection: "column", gap: 14 }}>
          {children}
        </div>
        <div className="thread-foot" style={{ paddingTop: 4 }}><Composer ph={composerPh} /></div>
      </div>
    </div>
  );
}

/* ---------- MAIN-widget building blocks ---------- */
const Panel = ({ title, children, style, chromeless }) => (
  <div className={"w-host" + (chromeless ? " chromeless" : "")} style={{ minHeight: 0, display: "flex", flexDirection: "column", ...style }}>
    {title && <div className="w-head"><span className="lbl">{title}</span></div>}
    <div style={{ minHeight: 0, overflow: "hidden", flex: 1 }}>{children}</div>
  </div>
);

const Metrics = ({ cells }) => (
  <div style={{ display: "grid", gridTemplateColumns: `repeat(${cells.length}, 1fr)`, gap: 12 }}>
    {cells.map((c, i) => (
      <div key={i} className="w-metric">
        <div className="m-label">{c.label}</div>
        <div className="m-row"><div className="m-value" style={{ fontSize: 22 }}>{c.value}</div>
          {c.delta != null && <span className={"w-delta " + (c.delta > 0 ? "up" : "down")}>{c.delta > 0 ? "▲" : "▼"} {Math.abs(c.delta)}</span>}</div>
        {c.hint && <div className="m-hint">{c.hint}</div>}
      </div>
    ))}
  </div>
);

const ToolLog = ({ tools }) => (
  <ul className="w-tools" style={{ listStyle: "none", margin: 0, padding: 0 }}>
    {tools.map((t, i) => (
      <li key={i} className="w-tool">
        <div className="w-tool-row" style={{ padding: "8px 11px", cursor: "default" }}>
          <span className={"w-dot " + t.s} /><span className="t-name">{t.name}</span><span className="t-args">{t.args}</span>
          <span className="t-toggle">{t.s === "running" ? "" : "show"}</span>
        </div>
      </li>
    ))}
  </ul>
);

const DataTable = ({ head, rows, foot }) => (
  <>
    <div className="w-table-wrap">
      <table className="w-table">
        <thead><tr>{head.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
    {foot && <div className="w-table-foot">{foot}</div>}
  </>
);
const StatusCell = ({ ok }) => <span style={{ color: ok ? "var(--ok)" : "var(--danger)", fontWeight: 600, fontSize: 12 }}>● {ok ? "matched" : "flag"}</span>;
const Num = ({ children }) => <span className="num">{children}</span>;

/* transcript pieces — prototype design verbatim */
const UserMsg = ({ children }) => (
  <div className="msg user"><div className="msg-body" style={{ display: "flex", justifyContent: "flex-end" }}><div className="ucard">{children}</div></div></div>
);
const AgentMsg = ({ agent, time = "9:14 AM", caret, children }) => (
  <div className="msg assistant">
    <Glyph a={agent} size={30} r={8} />
    <div className="msg-body">
      <div className="bubble-meta"><b>{agent.name}</b><span className="hero-rule" style={{ width: 20, height: 2, margin: 0, background: agent.c }} /><span className="t">{time}</span></div>
      {children}{caret && <span className="caret" />}
      {!caret && <div className="actions in"><span className="act"><Icons.copy s={15} /></span><span className="act"><Icons.refresh s={15} /></span></div>}
    </div>
  </div>
);
const ThinkMsg = ({ agent, status }) => (
  <div className="msg assistant">
    <Glyph a={agent} size={30} r={8} cls="think" />
    <div className="msg-body">
      <div className="bubble-meta"><b>{agent.name}</b><span className="hero-rule" style={{ width: 20, height: 2, margin: 0, background: agent.c }} /><span className="t">now</span></div>
      <div className="composing"><div className="goo"><span className="d1" /><span className="d2" /><span className="d3" /></div><div className="working shimmer">{status}…</div></div>
    </div>
  </div>
);
const CodeBlk = ({ name, lines }) => (
  <div className="codeblk"><div className="cb-head"><Icons.doc s={14} /><span className="lbl">{name}</span></div>
    <pre>{lines.map(([k, v], i) => <div key={i}><span className="k">{k}</span>: <span className="s">{v}</span></div>)}</pre></div>
);
const Transcript = ({ children, style }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 22, overflow: "hidden", ...style }}>{children}</div>
);

/* ============================================================
   A · ATLAS — incident response console
   ============================================================ */
function AtlasLayout({ theme = "dark" }) {
  const a = byId("atlas");
  return (
    <Frame theme={theme} accent="mono">
      <Shell agent={a} theme={theme} title="checkout-service · p99 incident" composerPh="Reply to Atlas"
        history={["checkout p99 incident", "auth latency regression", "cron backlog drain", "deploy rollback b3f9c2"]}
        filesLabel="Runbooks" files={[
          { name: "incident-checklist.md", size: "3.1 KB" }, { name: "rollback.yaml", size: "0.6 KB", sel: true },
          { name: "oncall-rota.md", size: "1.2 KB" }, { name: "slo-budget.md", size: "2.0 KB" },
        ]}>
        <Metrics cells={[
          { label: "p99 latency", value: "880ms", delta: 21, hint: "was 40ms" },
          { label: "Error rate", value: "2.4%", delta: 2 },
          { label: "Affected", value: "checkout", hint: "1 service" },
          { label: "Time to detect", value: "4m", hint: "since 14:30" },
        ]} />
        <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "minmax(0,1.55fr) minmax(0,1fr)", gap: 14 }}>
          <Panel chromeless>
            <Transcript>
              <UserMsg>checkout-service p99 latency spiked at 14:30. Trace it and tell me what to roll back.</UserMsg>
              <AgentMsg agent={a}>
                <p>The spike traces to one dependency. <b>payment-gateway</b> calls jumped from a 40&nbsp;ms median to 880&nbsp;ms right after deploy <span className="mono" style={{ color: "var(--accent-2)" }}>b3f9c2</span> — it added a synchronous fraud-check hop with no timeout.</p>
                <CodeBlk name="rollback.yaml" lines={[["target", "checkout-service"], ["action", "rollback"], ["to_revision", '"a17d04"']]} />
              </AgentMsg>
            </Transcript>
          </Panel>
          <Panel title="Tool calls"><ToolLog tools={[
            { s: "done", name: "get_traces", args: "· 14:25–14:40" },
            { s: "done", name: "correlate_deploys", args: "· last 6" },
            { s: "running", name: "check_slo_budget", args: "· checkout" },
          ]} /></Panel>
        </div>
      </Shell>
    </Frame>
  );
}

/* ============================================================
   B · FORGE — coding agent workspace
   ============================================================ */
function ForgeLayout({ theme = "dark" }) {
  const a = byId("forge");
  return (
    <Frame theme={theme} accent="mono">
      <Shell agent={a} theme={theme} title="ci-pipeline · cache refactor" composerPh="Tell Forge what to build"
        history={["CI cache refactor", "flaky test triage", "dependency bump", "dockerfile slimming"]}
        filesLabel="Repository" files={[
          { folder: true, open: true, name: "src" }, { d: 1, name: "index.ts", size: "2.1 KB" },
          { d: 1, folder: true, open: true, name: "ci" }, { d: 2, name: "build.yaml", size: "1.2 KB", sel: true },
          { d: 2, name: "test.yaml", size: "0.8 KB" }, { name: "README.md", size: "6.0 KB" },
        ]}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="mono" style={{ fontSize: 12.5, color: "var(--text-2)" }}><Icons.layers s={14} style={{ verticalAlign: -2, marginRight: 6 }} />feature/ci-cache</span>
          <span className="spacer" />
          <button className="w-btn w-btn-default sm">Open PR</button>
          <button className="w-btn w-btn-outline sm">Run CI</button>
          <button className="w-btn w-btn-ghost sm">Discard</button>
        </div>
        <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "minmax(0,1.5fr) minmax(0,1fr)", gap: 14 }}>
          <Panel chromeless>
            <Transcript>
              <UserMsg>Refactor the CI to cache the docker layers between jobs.</UserMsg>
              <AgentMsg agent={a}>
                <p>I'll split the build into a warm-cache job and parallel test shards so layers are reused between runs:</p>
                <CodeBlk name=".ci/build.yaml" lines={[["cache.key", "docker-{{ hash }}"], ["cache.paths", "[/var/lib/docker]"], ["jobs", "[build, test×4, scan]"]]} />
                <p>Estimated wall-clock drops from ~3m12s to ~1m04s.</p>
              </AgentMsg>
            </Transcript>
          </Panel>
          <Panel title="Tool calls"><ToolLog tools={[
            { s: "done", name: "read_file", args: "· .ci/build.yaml" },
            { s: "done", name: "edit_file", args: "· +cache.key" },
            { s: "done", name: "write_file", args: "· test.yaml" },
            { s: "running", name: "run_ci", args: "· dry-run" },
          ]} /></Panel>
        </div>
      </Shell>
    </Frame>
  );
}

/* ============================================================
   C · LEDGER — finance reconciliation
   ============================================================ */
function LedgerLayout({ theme = "dark" }) {
  const a = byId("ledger");
  const rows = [
    [<Num>INV-2041</Num>, "Northwind", <Num>$12,400</Num>, <StatusCell ok />],
    [<Num>INV-2042</Num>, "Acme Corp", <Num>$3,180</Num>, <StatusCell />],
    [<Num>INV-2043</Num>, "Globex", <Num>$8,650</Num>, <StatusCell ok />],
    [<Num>INV-2044</Num>, "Initech", <Num>$1,920</Num>, <StatusCell />],
    [<Num>INV-2045</Num>, "Umbrella", <Num>$5,210</Num>, <StatusCell ok />],
  ];
  return (
    <Frame theme={theme} accent="mono">
      <Shell agent={a} theme={theme} title="May · wk-22 batch" composerPh="Ask Ledger about finance ops"
        history={["wk-22 batch", "Q1 vendor audit", "spend forecast", "duplicate detection"]}
        filesLabel="Statements" files={[
          { name: "invoices.csv", size: "84 KB" }, { name: "po-register.csv", size: "42 KB" },
          { name: "vendors.csv", size: "9 KB" }, { name: "tolerance-policy.md", size: "1.1 KB" },
        ]}>
        <Metrics cells={[
          { label: "Batch total", value: "$26.1K", hint: "31 invoices" },
          { label: "Matched", value: "94%", delta: 2 },
          { label: "Flagged", value: "2", delta: -1 },
          { label: "Avg variance", value: "$640", hint: "over tolerance" },
        ]} />
        <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "minmax(0,1.5fr) minmax(0,1fr)", gap: 14 }}>
          <Panel title="Invoice reconciliation">
            <DataTable head={["invoice", "vendor", "amount", "status"]} rows={rows} foot="Showing 5 of 31 rows (head)" />
          </Panel>
          <Panel chromeless>
            <Transcript>
              <UserMsg>Reconcile this batch and flag mismatches.</UserMsg>
              <AgentMsg agent={a}>
                <p>This batch reconciles cleanly except for two invoices where the PO and received amounts diverge past tolerance. Both are from the same vendor — a unit-vs-case pricing mismatch. I've drafted a query to procurement.</p>
              </AgentMsg>
            </Transcript>
          </Panel>
        </div>
      </Shell>
    </Frame>
  );
}

/* ============================================================
   D · PROBE — research desk
   ============================================================ */
function ProbeLayout({ theme = "dark" }) {
  const a = byId("probe");
  return (
    <Frame theme={theme} accent="mono">
      <Shell agent={a} theme={theme} title="Vendor pricing brief" composerPh="Ask Probe to research or retrieve"
        history={["Vendor pricing brief", "Compliance scan", "Competitor teardown", "Market sizing"]}
        filesLabel="Documents" files={[
          { name: "pricing-2026.pdf", size: "1.4 MB", sel: true }, { name: "vendor-b-tiers.md", size: "12 KB" },
          { name: "rfp-notes.txt", size: "4 KB" }, { name: "seat-counts.csv", size: "2 KB" },
        ]}>
        <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "minmax(0,1.6fr) minmax(0,1fr)", gap: 14 }}>
          <Panel chromeless>
            <Transcript>
              <UserMsg>Summarize how the three leading vendors price their agent platforms.</UserMsg>
              <AgentMsg agent={a}>
                <p>Pricing splits along one axis: <b>seats</b> versus <b>runs</b>. Two anchor to a per-seat subscription with metered overage; the third bills purely per agent execution.</p>
                <p>For a wide internal rollout with modest per-user volume, the per-seat vendors stay materially cheaper at scale. Sources pulled into the workspace.</p>
              </AgentMsg>
              <ThinkMsg agent={a} status="Ranking sources" />
            </Transcript>
          </Panel>
          <Panel title="Sources">
            <div className="w-md" style={{ fontSize: 13.5 }}>
              <ul style={{ paddingLeft: 18, marginTop: 0 }}>
                <li><a href="#">pricing-2026.pdf</a> · p.4 tiers</li>
                <li><a href="#">vendor-b-tiers.md</a></li>
                <li><a href="#">rfp-notes.txt</a> · §pricing</li>
              </ul>
              <blockquote style={{ fontSize: 12.5 }}>Per-seat stays cheaper for wide, low-volume rollouts.</blockquote>
              <p style={{ fontSize: 12.5 }}>3 documents · ranked by relevance to <code>pricing</code>.</p>
            </div>
          </Panel>
        </div>
      </Shell>
    </Frame>
  );
}

/* ============================================================
   E · RELAY — integration builder
   ============================================================ */
function RelayLayout({ theme = "dark" }) {
  const a = byId("relay");
  return (
    <Frame theme={theme} accent="mono">
      <Shell agent={a} theme={theme} title="CRM ↔ billing sync" composerPh="Ask Relay to connect or automate"
        history={["CRM ↔ billing sync", "Slack alert wiring", "webhook retries", "nightly export"]}
        filesLabel="Connectors" files={[
          { name: "crm.json", size: "3 KB" }, { name: "billing-api.json", size: "5 KB" },
          { name: "mappings.yaml", size: "1 KB", sel: true }, { name: "secrets.env", size: "0.3 KB" },
        ]}>
        <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "minmax(0,1.2fr) minmax(0,1fr)", gap: 14 }}>
          <div className="w-host" style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
            <div className="w-head"><span className="lbl">Configure sync</span></div>
            <div className="w-form" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <div className="w-field"><span className="f-label">Source<span className="req">*</span></span><div className="w-select">CRM · REST</div></div>
              <div className="w-field"><span className="f-label">Destination<span className="req">*</span></span><div className="w-select">Billing API</div></div>
              <div className="w-field"><span className="f-label">Schedule</span><input className="w-input" defaultValue="*/15 * * * *" /></div>
              <div className="w-field"><span className="f-label">Idempotency key</span><input className="w-input" defaultValue="external_id" /></div>
              <label className="w-check on" style={{ gridColumn: "1 / -1" }}><span className="box"><Icons.check s={13} /></span> Run a dry sync against staging first</label>
            </div>
            <div className="w-form-foot"><button className="w-btn w-btn-default">Run dry sync</button><button className="w-btn w-btn-outline">Promote to prod</button></div>
          </div>
          <Panel chromeless>
            <Transcript>
              <UserMsg>Wire a sync between the CRM and the billing system.</UserMsg>
              <AgentMsg agent={a}>
                <p>I can bridge the two with a scheduled sync. The source exposes a clean REST endpoint; the destination needs an idempotency key on each upsert to avoid duplicates. I'll dry-run against staging and report the diff before touching production.</p>
              </AgentMsg>
            </Transcript>
          </Panel>
        </div>
      </Shell>
    </Frame>
  );
}

Object.assign(window, { AtlasLayout, ForgeLayout, LedgerLayout, ProbeLayout, RelayLayout });
