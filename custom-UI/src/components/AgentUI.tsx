import { useEffect, useMemo, useState } from "react";
import type { Diagnostic } from "../diagnostics/types.js";
import { DiagnosticsOverlay } from "../diagnostics/Overlay.js";
import type { ActionDispatcher } from "../runtime/dispatcher.js";
import type { AgentBridge } from "../runtime/agentBridge.js";
import type { ThemeTokens } from "../compile/theme.js";
import { compilePlan, type RenderPlan } from "../compile/plan.js";
import { parseYaml } from "../compile/parse.js";
import type { SourceMap } from "../compile/parse.js";
import { WidgetRegistry } from "../registry/register.js";
import { builtinWidgets } from "../registry/builtin.js";
import type { AnyWidgetDefinition } from "../registry/types.js";
import { AgentUIProvider } from "../runtime/context.js";
import type { ConversationMessage } from "../runtime/context.js";
import { GridRoot } from "./layout/GridRoot.js";
import { FlexRoot } from "./layout/FlexRoot.js";
import { WidgetHost } from "./WidgetHost.js";

export interface AgentUIProps {
  /** Raw YAML string, already-parsed object, or fetchable URL. */
  config: string | object | URL;
  dispatcher: ActionDispatcher;
  /** Custom widget registry (extends builtins). Pass an array of defs or a WidgetRegistry. */
  widgets?: WidgetRegistry | AnyWidgetDefinition[];
  agent?: AgentBridge;
  theme?: Partial<ThemeTokens>;
  /** Seed the transcript with a previously-saved conversation's messages. */
  initialMessages?: ConversationMessage[];
  diagnostics?: "overlay" | "console" | "silent";
  onError?: (diagnostics: Diagnostic[]) => void;
}

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; plan: RenderPlan }
  | { kind: "error"; diagnostics: Diagnostic[] };

export function AgentUI(props: AgentUIProps): JSX.Element {
  const {
    config,
    dispatcher,
    widgets,
    agent,
    theme,
    initialMessages,
    diagnostics = "overlay",
    onError,
  } = props;

  const registry = useMemo(() => {
    if (widgets instanceof WidgetRegistry) return widgets;
    const r = new WidgetRegistry(builtinWidgets);
    if (Array.isArray(widgets)) r.registerMany(widgets);
    return r;
  }, [widgets]);

  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { raw, locate } = await loadConfig(config);
        const result = compilePlan(raw, {
          registry,
          dispatcher,
          ...(locate && { locate }),
          ...(theme && { themeOverride: theme }),
        });
        if (cancelled) return;
        if (!result.ok) {
          reportDiagnostics(result.errors, diagnostics, onError);
          setState({ kind: "error", diagnostics: result.errors });
          return;
        }
        if (result.value.diagnostics.length > 0) {
          reportDiagnostics(result.value.diagnostics, diagnostics, onError);
        }
        setState({ kind: "ready", plan: result.value });
      } catch (e) {
        const d: Diagnostic = {
          severity: "error",
          code: "agent-ui.load",
          message: e instanceof Error ? e.message : String(e),
          path: [],
        };
        reportDiagnostics([d], diagnostics, onError);
        if (!cancelled) setState({ kind: "error", diagnostics: [d] });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [config, registry, dispatcher, theme, diagnostics, onError]);

  // Hooks below this line must run on every render — never gate them with
  // conditional returns. Compute the mode regardless of load state so the
  // dark-mode listener mounts before the plan resolves.
  const mode: "light" | "dark" | "system" =
    state.kind === "ready" ? state.plan.theme.mode : "light";
  const darkActive = useDarkActive(mode);

  if (state.kind === "loading") {
    return <div className="au-root au-loading">Loading…</div>;
  }
  if (state.kind === "error") {
    return (
      <div className="au-root au-config-error">
        <div className="au-config-error-title">Configuration error</div>
        {diagnostics === "overlay" && (
          <DiagnosticsOverlay diagnostics={state.diagnostics} />
        )}
      </div>
    );
  }

  const plan = state.plan;
  const widgetNames = plan.widgets.map((w) => w.name);

  return (
    <AgentUIProvider
      dispatcher={dispatcher}
      {...(agent && { agent })}
      {...(initialMessages && { initialMessages })}
      knownWidgetNames={widgetNames}
    >
      <div
        className={[
          "au-root",
          `au-layout-${plan.layout.kind}`,
          darkActive ? "dark" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        style={plan.theme.cssVars as React.CSSProperties}
      >
        <div className="au-main-slot">
          {renderLayout(plan, dispatcher)}
        </div>
        {plan.footer.length > 0 && (
          <div className="au-footer-slot">
            {plan.footer.map((w) => (
              <WidgetHost key={w.id} widget={w} dispatcher={dispatcher} />
            ))}
          </div>
        )}
        {diagnostics === "overlay" && plan.diagnostics.length > 0 && (
          <DiagnosticsOverlay diagnostics={plan.diagnostics} />
        )}
      </div>
    </AgentUIProvider>
  );
}

/**
 * Resolves whether dark mode should be active right now.
 *  - "dark"   → always.
 *  - "light"  → never.
 *  - "system" → tracks the OS `prefers-color-scheme` media query.
 */
function useDarkActive(mode: "light" | "dark" | "system"): boolean {
  const [systemDark, setSystemDark] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  });

  useEffect(() => {
    if (mode !== "system") return;
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    setSystemDark(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [mode]);

  if (mode === "dark") return true;
  if (mode === "light") return false;
  return systemDark;
}

function renderLayout(plan: RenderPlan, dispatcher: ActionDispatcher): JSX.Element {
  switch (plan.layout.kind) {
    case "grid":
      return <GridRoot plan={plan} dispatcher={dispatcher} />;
    case "flex":
      return <FlexRoot plan={plan} dispatcher={dispatcher} />;
  }
}

async function loadConfig(
  config: string | object | URL,
): Promise<{ raw: unknown; locate?: SourceMap }> {
  if (config instanceof URL) {
    const res = await fetch(config);
    if (!res.ok) throw new Error(`Failed to fetch config: ${res.status}`);
    const text = await res.text();
    return parseText(text);
  }
  if (typeof config === "string") {
    // Heuristic: treat a string containing a newline or YAML scaffolding as
    // raw YAML; otherwise try to fetch.
    if (looksLikeYaml(config)) return parseText(config);
    const res = await fetch(config);
    if (!res.ok) throw new Error(`Failed to fetch config: ${res.status}`);
    return parseText(await res.text());
  }
  return { raw: config };
}

function parseText(text: string): { raw: unknown; locate?: SourceMap } {
  const r = parseYaml(text);
  if (!r.ok) {
    const msg = r.errors.map((e) => e.message).join("; ");
    throw new Error(`YAML parse error: ${msg}`);
  }
  return { raw: r.value.data, locate: r.value.locate };
}

function looksLikeYaml(s: string): boolean {
  return s.includes("\n") || /^[\w-]+:\s/.test(s);
}

function reportDiagnostics(
  diags: Diagnostic[],
  mode: "overlay" | "console" | "silent",
  onError?: (d: Diagnostic[]) => void,
): void {
  if (onError && diags.some((d) => d.severity === "error")) {
    onError(diags);
  }
  if (mode === "console") {
    for (const d of diags) {
      const loc =
        d.sourceLine !== undefined ? ` (line ${d.sourceLine})` : "";
      const msg = `[agent-ui ${d.severity}] ${d.code}: ${d.message}${loc}`;
      if (d.severity === "error") console.error(msg);
      else console.warn(msg);
    }
  }
}
