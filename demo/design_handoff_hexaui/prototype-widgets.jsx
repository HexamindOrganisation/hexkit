/* prototype-widgets.jsx — per-agent MAIN-widget layouts for the live
   prototype. The chat (ai-response + composer) stays constant and centered;
   each agent surrounds it with the widgets a developer would configure in
   YAML for that agent's job. Everything inherits the active --accent, so it
   recolors with the selected agent automatically.

   Wrapped in an IIFE to avoid colliding with the top-level `const Icons`
   already declared in icons.jsx. Exports window.AgentWidgets:
     { [agentId]: { top?(ctx), side?(ctx), sideTitle, sideWidth } }
   ctx = { pending } so the tool log can show a live "running" row. */
(function () {
  const { Icons } = window;

  /* ---- reusable panel pieces (raw widget CSS classes) ---- */
  const MetricsStrip = (cells) => (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${cells.length}, 1fr)`, gap: 12 }}>
      {cells.map((c, i) => (
        <div key={i} className="w-metric">
          <div className="m-label">{c.label}</div>
          <div className="m-row">
            <div className="m-value" style={{ fontSize: 22 }}>{c.value}</div>
            {c.delta != null && <span className={"w-delta " + (c.delta > 0 ? "up" : "down")}>{c.delta > 0 ? "▲" : "▼"} {Math.abs(c.delta)}</span>}
          </div>
          {c.hint && <div className="m-hint">{c.hint}</div>}
        </div>
      ))}
    </div>
  );

  const ActionBar = (crumb, buttons) => (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span className="mono" style={{ fontSize: 12.5, color: "var(--text-2)" }}>
        <Icons.layers s={14} style={{ verticalAlign: -2, marginRight: 6 }} />{crumb}
      </span>
      <span className="spacer" style={{ flex: 1 }} />
      {buttons.map(([label, v], i) => <button key={i} className={"w-btn w-btn-" + v + " sm"}>{label}</button>)}
    </div>
  );

  const ToolList = (tools) => (
    <ul className="w-tools" style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {tools.map((t, i) => (
        <li key={i} className="w-tool">
          <div className="w-tool-row" style={{ padding: "8px 11px", cursor: "default" }}>
            <span className={"w-dot " + t.s} />
            <span className="t-name">{t.name}</span>
            {t.args && <span className="t-args">{t.args}</span>}
            <span className="t-toggle">{t.s === "running" ? "…" : "show"}</span>
          </div>
        </li>
      ))}
    </ul>
  );

  const Num = ({ children }) => <span className="num">{children}</span>;
  const Status = ({ ok }) => <span style={{ color: ok ? "var(--ok)" : "var(--danger)", fontWeight: 600, fontSize: 12 }}>● {ok ? "matched" : "flag"}</span>;

  const InvoiceTable = () => {
    const rows = [
      ["INV-2041", "Northwind", "$12,400", true], ["INV-2042", "Acme Corp", "$3,180", false],
      ["INV-2043", "Globex", "$8,650", true], ["INV-2044", "Initech", "$1,920", false],
      ["INV-2045", "Umbrella", "$5,210", true], ["INV-2046", "Soylent", "$2,470", true],
    ];
    return (
      <>
        <div className="w-table-wrap">
          <table className="w-table">
            <thead><tr><th>invoice</th><th>vendor</th><th>amount</th><th>status</th></tr></thead>
            <tbody>{rows.map((r, i) => (
              <tr key={i}><td><Num>{r[0]}</Num></td><td>{r[1]}</td><td><Num>{r[2]}</Num></td><td><Status ok={r[3]} /></td></tr>
            ))}</tbody>
          </table>
        </div>
        <div className="w-table-foot">Showing 6 of 31 rows (head)</div>
      </>
    );
  };

  const Sources = () => (
    <div className="w-md" style={{ fontSize: 13.5 }}>
      <ul style={{ paddingLeft: 18, marginTop: 0 }}>
        <li><a href="#">pricing-2026.pdf</a> · p.4 tiers</li>
        <li><a href="#">vendor-b-tiers.md</a></li>
        <li><a href="#">rfp-notes.txt</a> · §pricing</li>
      </ul>
      <blockquote style={{ fontSize: 12.5 }}>Per-seat stays cheaper for wide, low-volume rollouts.</blockquote>
      <p style={{ fontSize: 12.5 }}>3 documents · ranked by relevance to <code>pricing</code>.</p>
    </div>
  );

  const SyncForm = () => (
    <>
      <div className="w-form" style={{ gridTemplateColumns: "1fr" }}>
        <div className="w-field"><span className="f-label">Source<span className="req">*</span></span><div className="w-select">CRM · REST</div></div>
        <div className="w-field"><span className="f-label">Destination<span className="req">*</span></span><div className="w-select">Billing API</div></div>
        <div className="w-field"><span className="f-label">Schedule</span><input className="w-input" defaultValue="*/15 * * * *" /></div>
        <div className="w-field"><span className="f-label">Idempotency key</span><input className="w-input" defaultValue="external_id" /></div>
        <label className="w-check on"><span className="box"><Icons.check s={13} /></span> Dry sync against staging first</label>
      </div>
      <div className="w-form-foot" style={{ marginTop: 14 }}>
        <button className="w-btn w-btn-default">Run dry sync</button>
        <button className="w-btn w-btn-outline">Promote</button>
      </div>
    </>
  );

  /* ---- per-agent layouts ---- */
  window.AgentWidgets = {
    atlas: {
      top: () => MetricsStrip([
        { label: "p99 latency", value: "880ms", delta: 21, hint: "was 40ms" },
        { label: "Error rate", value: "2.4%", delta: 2 },
        { label: "Affected", value: "checkout", hint: "1 service" },
        { label: "Time to detect", value: "4m", hint: "since 14:30" },
      ]),
      sideTitle: "Tool calls", sideWidth: 322,
      side: (ctx) => ToolList([
        { s: "done", name: "get_traces", args: "· 14:25–14:40" },
        { s: "done", name: "correlate_deploys", args: "· last 6" },
        { s: ctx.pending ? "running" : "done", name: "check_slo_budget", args: "· checkout" },
      ]),
    },
    forge: {
      top: () => ActionBar("feature/ci-cache", [["Open PR", "default"], ["Run CI", "outline"], ["Discard", "ghost"]]),
      sideTitle: "Tool calls", sideWidth: 340,
      side: (ctx) => ToolList([
        { s: "done", name: "read_file", args: "· .ci/build.yaml" },
        { s: "done", name: "edit_file", args: "· +cache.key" },
        { s: "done", name: "write_file", args: "· test.yaml" },
        { s: ctx.pending ? "running" : "done", name: "run_ci", args: "· dry-run" },
      ]),
    },
    ledger: {
      top: () => MetricsStrip([
        { label: "Batch total", value: "$26.1K", hint: "31 invoices" },
        { label: "Matched", value: "94%", delta: 2 },
        { label: "Flagged", value: "2", delta: -1 },
        { label: "Avg variance", value: "$640", hint: "over tolerance" },
      ]),
      sideTitle: "Invoice reconciliation", sideWidth: 430,
      side: () => <InvoiceTable />,
    },
    probe: {
      top: null,
      sideTitle: "Sources", sideWidth: 320,
      side: () => <Sources />,
    },
    relay: {
      top: null,
      sideTitle: "Configure sync", sideWidth: 380,
      side: () => <SyncForm />,
    },
    sentry: {
      top: () => MetricsStrip([
        { label: "Fleet", value: "6/6", hint: "agents healthy" },
        { label: "Alerts armed", value: "3" },
        { label: "Retry rate", value: "0.4/m", delta: 1 },
        { label: "Error budget", value: "82%", hint: "month to date" },
      ]),
      sideTitle: "Recent audits", sideWidth: 322,
      side: (ctx) => ToolList([
        { s: "done", name: "poll_fleet", args: "· 6 agents" },
        { s: "done", name: "check_budgets", args: "" },
        { s: ctx.pending ? "running" : "done", name: "arm_alert", args: "· Relay retry×2" },
      ]),
    },
  };
})();
