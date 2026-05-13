# agent-ui — Full Specification & Implementation Plan

> A React + TypeScript library that turns a YAML config into a running AI agent UI.
> Working name: **agent-ui** (rename freely).
> This document is self-contained and meant to be fed to an implementing agent.

---

## 1. Vision & Scope

**Goal:** developers describe an AI agent's interface in a YAML file. The library
loads the YAML, validates it, compiles a render plan, and renders the UI in React.
Two default containers (**user input**, **agent response**) are always present; all
other UI is contributed as **widgets** from a catalog that the host can extend.

**In scope (v1):**
- YAML → render pipeline (parse, validate, resolve, compile, render).
- Two default containers: user input, agent response.
- Built-in widget catalog (~5–7 widgets).
- Extensible widget registry for host-defined widgets.
- Pluggable action dispatcher (agent tools, HTTP, or local fns — host's choice).
- JSON Schema export for YAML editor autocomplete.
- Streaming agent events → containers & widgets via optional `AgentBridge`.

**Out of scope (v1):**
- Hosted platform / runtime service.
- Visual editor / drag-and-drop builder.
- Built-in auth, persistence, or agent framework.
- Full design system — ships unstyled primitives + theme variables.
- Inter-widget communication (widgets are isolated in v1).
- Nested / composite widgets (flat `widgets[]` only).
- i18n (strings pass through verbatim).
- Production hot reload (dev-only watch mode).

---

## 2. Locked Architectural Decisions

These were decided up front and ripple through every phase — do not deviate
without revisiting the spec.

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Library-first**, not a hosted platform. Ship as an npm package (`<AgentUI />` component + registration APIs). | Lowest risk, integrates anywhere, hosted runtime can come later once the schema stabilizes. |
| 2 | **React + TypeScript**. | User's stack choice. |
| 3 | **JSON Schema** for validation (Ajv runtime + `json-schema-to-ts` for compile-time TS types). Discriminated unions via `oneOf` + `const` tag. | Portable artifact (can be exported for backend/IDE), single source of truth for runtime + TS types. |
| 4 | **Widgets are isolated in v1.** No shared state bus, no widget-to-widget messaging. All coordination goes through the dispatcher. | Keeps the v1 contract small and honest. Revisit in v1.1 if demand emerges. |
| 5 | **Flat widgets only.** No nesting/composition. | Defer to v2. |
| 6 | **No i18n.** Strings pass through verbatim. | Host can preprocess. |
| 7 | **Icons: URLs and data URIs only.** No bundler integration. | Keeps the library framework-agnostic. |
| 8 | **No production hot reload.** Config is effectively build-time. Dev-only watch. | |
| 9 | **Dispatcher is host-controlled.** Action names treated as trusted. | Injection risk is the host's responsibility. |
| 10 | **`AgentBridge` is optional.** `<AgentUI>` mounts without it; containers fall back to passive mode. | Non-streaming apps can skip the bridge entirely. |
| 11 | **Tool-call routing is name-only and strict.** `tool-call` events require a `widget` field naming the target. No broadcast. | Preserves the widget-isolation guarantee. |

---

## 3. Processing Pipeline

```
  YAML text
     |
  [1] parse       — yaml (eemeli/yaml, preserves line/col)
     |
  [2] validate    — Ajv (JSON Schema)       (unknown → Config)
     |
  [3] resolve     — registry + dispatcher   (Config → ResolvedConfig + Diagnostic[])
     |
  [4] normalize   — defaults, theme         (pure)
     |
  [5] compile     — layout math             (→ RenderPlan)
     |
  [6] render      — <AgentUI plan={...} />  (React)
     |
  [7] runtime     — dispatch, subscribe, agent bridge
```

Stages 1–5 are **pure functions** over data and return
`Result<T, Diagnostic[]>` — no throws inside the pipeline.
Stage 6 is React. Stage 7 is the only stateful/effectful layer.

**Why a separate `RenderPlan`:** it's serializable, snapshot-testable, and the
boundary for hot reload. Change the YAML → re-run steps 1–5 → diff the plan →
React reconciles.

---

## 4. Package Layout

```
agent-ui/
├── src/
│   ├── schema/          # JSON Schemas + FromSchema-inferred types
│   │   ├── page.ts
│   │   ├── widgets/     # one file per built-in widget schema
│   │   ├── common.ts    # Position, Size, Action, Icon
│   │   └── index.ts     # root ConfigSchema
│   ├── compile/
│   │   ├── resolve.ts   # stage 3
│   │   ├── normalize.ts # stage 4
│   │   ├── plan.ts      # stage 5
│   │   └── layout/      # grid | flex | sidebar | tabs compilers
│   ├── registry/
│   │   ├── builtin.ts
│   │   └── register.ts
│   ├── runtime/
│   │   ├── dispatcher.ts
│   │   ├── agentBridge.ts
│   │   └── subscriptions.ts
│   ├── components/
│   │   ├── AgentUI.tsx
│   │   ├── WidgetHost.tsx
│   │   ├── containers/  # UserInput, AgentResponse
│   │   └── layout/      # GridRoot, FlexRoot, SidebarRoot, TabsRoot
│   ├── widgets/         # built-in widget components
│   ├── diagnostics/     # Diagnostic type, overlay
│   ├── cli/             # agent-ui emit-schema, validate
│   └── index.ts         # public API
├── examples/
│   ├── minimal/
│   ├── file-browser/
│   └── todo-agent/
├── tests/
│   ├── fixtures/        # valid + invalid YAML configs
│   └── plan.snap.test.ts
├── package.json
├── tsconfig.json
├── vite.config.ts       # library mode
└── README.md
```

---

## 5. Public API

```ts
// Primary mount point
export function AgentUI(props: {
  config: string | object | URL;            // raw YAML, parsed obj, or fetchable
  dispatcher: ActionDispatcher;
  widgets?: WidgetRegistry;                  // extends builtins
  agent?: AgentBridge;                       // optional; for streaming
  theme?: Partial<ThemeTokens>;              // override theme
  diagnostics?: "overlay" | "console" | "silent";
  onError?: (diagnostics: Diagnostic[]) => void;
}): JSX.Element;

// Action dispatcher contract (host implements)
export interface ActionDispatcher {
  invoke(action: string, args?: unknown): Promise<unknown>;
  subscribe?(action: string, args: unknown,
             onData: (d: unknown) => void): () => void;
  has?(action: string): boolean;  // for the resolver cross-check
}

// Widget registration (for custom widget types). `schema` is a JSON Schema
// object declared with `as const`; pass `TProps` as `FromSchema<typeof schema>`.
export function defineWidget<TProps>(spec: {
  type: string;
  schema: object;
  component: React.ComponentType<WidgetProps<TProps>>;
  defaults?: Partial<TProps>;
}): AnyWidgetDefinition;

// Widget runtime hooks
export function useWidgetData<T>(dataSource: DataSource): {
  data: T | undefined; loading: boolean; error?: Error;
};

export function useAgentInbox<TPayload>(): {
  lastPayload: TPayload | undefined;
  history: TPayload[];
};

// Schema export
export { ConfigSchema } from "./schema";

// CLI (bin)
//   agent-ui emit-schema > agent-ui.schema.json
//   agent-ui validate ./ui.yaml
```

### AgentBridge (optional)

```ts
export interface AgentBridge {
  onUserSubmit: (text: string) => void | Promise<void>;
  subscribeAgentOutput: (cb: (event: AgentEvent) => void) => () => void;
}

export type AgentEvent =
  | { kind: "token";     text: string; messageId?: string }
  | { kind: "message";   role: "assistant" | "system"; content: string; messageId?: string }
  | { kind: "status";    state: "idle" | "thinking" | "responding" }
  | { kind: "tool-call"; widget: string; payload: unknown }  // widget name REQUIRED
  | { kind: "error";     message: string };
```

### AgentEvent routing table

| Event kind  | Routed to                                                        |
|-------------|------------------------------------------------------------------|
| `token`     | `AgentResponse` container (coalesced by `messageId` if present)  |
| `message`   | `AgentResponse` container (finalized bubble)                     |
| `status`    | `AgentResponse` container (typing indicator, etc.)               |
| `tool-call` | The `WidgetHost` whose widget `name === event.widget`, only      |
| `error`     | `AgentResponse` + diagnostics bus (dev overlay in dev mode)      |

**Name-only routing, strictly.** `widget` is **required** on `tool-call`.
Events with no match log a dev-mode warning and drop — no broadcast, no
fallback widget. This preserves the widget-isolation guarantee.

### Fallback when `agent` prop is absent

- **UserInput container**: renders a submit form. On submit, calls
  `dispatcher.invoke("user-submit", { text })` if that action is registered;
  otherwise renders read-only with a dev warning.
- **AgentResponse container**: renders an empty placeholder slot.
- **Tool-call events**: unreachable — the bridge is the only source.

### Bridge lifecycle

- `subscribeAgentOutput` returns an unsubscribe fn; `<AgentUI>` calls it on unmount.
- Bridge identity is treated as stable per mount — changing the `agent` prop
  triggers unsubscribe + resubscribe.
- No retry/backoff in the library; the bridge is the host's responsibility.

---

## 6. YAML Schema (v1)

### Top-level shape

```yaml
page:
  title: string
  icon?: string                # URL or data URI
  main_color?: string          # hex, drives derived palette
  layout_type: grid | flex | sidebar | tabs
  theme?:                      # optional explicit overrides
    background?: string
    foreground?: string
    accent?: string
  main_menu?:
    - name: string
      icon?: string
      action: string

widgets:
  - name: string               # unique id, addressable from agent
    type: string               # discriminator
    position?:
      horizontal: left | right | center
      vertical: high | low | middle
    size:
      width: 1..12              # grid cols; ignored by non-grid layouts
      height: number            # px, or "auto"
    # ...type-specific fields (discriminated by `type`)
```

**Reserved names:** `user-input` and `agent-response` are the default containers
and must not appear in the `widgets[]` list. Their slots are determined by
`layout_type`.

### Built-in widget types for v1

| `type`            | purpose                             |
|-------------------|-------------------------------------|
| `file-type`       | File list with per-row action menu  |
| `to-do-list-type` | Checkable tasks                     |
| `markdown`        | Rendered markdown (static or live)  |
| `data-table`      | Tabular data with sort/filter       |
| `form`            | Input form → submit action          |
| `key-value`       | Labeled facts / status panel        |
| `chart`           | Line/bar (minimal, one lib)         |

### Example config (the original user example, annotated)

```yaml
page:
  title: "My Dashboard"
  icon: "assets/icons/app-icon.svg"
  main_color: "#2E86DE"
  layout_type: "grid"
  main_menu:
    - name: "Home"
      action: "navigate_home"
    - name: "Files"
      action: "open_files_view"
    - name: "Tasks"
      action: "open_tasks_view"
    - name: "Settings"
      action: "open_settings"
    - name: "Logout"
      action: "logout_user"

widgets:
  - name: "My Files"
    type: "file-type"
    position:
      horizontal: "left"
      vertical: "high"
    size:
      width: 6
      height: 400
    data_source:
      action: "list_user_files"
    file_actions:
      - icon: "assets/icons/open.svg"
        name: "Open"
        action: "open_file"
      - icon: "assets/icons/download.svg"
        name: "Download"
        action: "download_file"
      - icon: "assets/icons/share.svg"
        name: "Share"
        action: "share_file"
      - icon: "assets/icons/rename.svg"
        name: "Rename"
        action: "rename_file"
      - icon: "assets/icons/delete.svg"
        name: "Delete"
        action: "delete_file"

  - name: "My Tasks"
    type: "to-do-list-type"
    position:
      horizontal: "right"
      vertical: "high"
    size:
      width: 6
      height: 400
```

---

## 7. Core Types

```ts
// Post-validation
type Config = FromSchema<typeof ConfigSchema>;

// Post-resolution: actions & widget types have been cross-checked
type ResolvedWidget = {
  id: string;                    // = widget.name
  type: string;
  props: unknown;                // typed by the widget's own schema
  position: Position;
  size: Size;
  component: React.ComponentType<WidgetProps<unknown>>;
};

type RenderPlan = {
  theme: ResolvedTheme;          // -> CSS custom properties
  chrome: { title: string; icon?: string; menu: MenuItem[] };
  layout: LayoutPlan;            // discriminated per layout_type
  widgets: ResolvedWidget[];
  containers: {
    userInput: { slot: string };
    agentResponse: { slot: string };
  };
};

type Diagnostic = {
  severity: "error" | "warning";
  code: string;                  // e.g., "unknown-action", "grid-collision"
  message: string;
  path: (string | number)[];     // JSON path into config
  sourceLine?: number;           // for YAML overlay
  sourceCol?: number;
};

type LayoutPlan =
  | { kind: "grid";    template: GridTemplate;    cells: GridCell[] }
  | { kind: "flex";    direction: "row" | "column"; items: FlexItem[] }
  | { kind: "sidebar"; menu: MenuItem[]; main: LayoutPlan }
  | { kind: "tabs";    tabs: { id: string; label: string; content: LayoutPlan }[] };
```

---

## 8. Layout Engine

Each layout compiles position/size into concrete CSS:

- **grid** — 12-column CSS Grid. Position hints (`left/right/high/low`) bias the
  packer; `size.width` determines column span. Solver packs top-down,
  left-to-right, with collision detection. Start greedy, iterate.
- **flex** — ignores `position`; stacks in config order. `size.width` becomes
  percentage of container.
- **sidebar** — `main_menu` becomes left nav; widgets fill main area using
  grid rules.
- **tabs** — widgets grouped by optional `tab` field become tab panels; default
  containers stay persistent above/below.

The grid solver is the trickiest piece — start with a greedy packer, add
collision diagnostics, iterate as fixtures demand.

---

## 9. Theming

- `main_color` → derive a palette (lighten/darken or HSL rotations) → CSS
  custom properties on `<AgentUI>` root.
- No CSS-in-JS dependency. Ship a single stylesheet + CSS variables.
- Host can override any token via the `theme` prop or by redefining variables.

**Tokens:** `--au-bg`, `--au-fg`, `--au-accent`, `--au-accent-fg`,
`--au-border`, `--au-radius`, `--au-space-1..5`, `--au-font`.

---

## 10. Runtime

### Action flow

```
widget → dispatch("action-name", args)
       → dispatcher.invoke → host's agent tool / HTTP / local fn
       → result (or stream via subscribe)
```

### Agent bridge flow

```
agent tokens → subscribeAgentOutput → AgentResponseContainer
user submit  → onUserSubmit          → host (triggers agent turn)
agent tool-call.widget === "X"       → WidgetHost for "X" only
```

Widgets read data via a hook:

```ts
const { data, loading, error } = useWidgetData(dataSource);
```

Backed by `dispatcher.subscribe` if available, else `invoke` with revalidation.

Widgets opt in to tool-call inbox via:

```ts
const { lastPayload, history } = useAgentInbox<TPayload>();
```

Scoped to the widget's own `name`. A widget can never observe another widget's
inbox.

---

## 11. Error Handling

- Stages 1–5 return `Result<T, Diagnostic[]>`. No throws inside the pipeline.
- Ajv errors map to `Diagnostic[]` (codes prefixed `ajv.*`) with YAML source
  locations (line/col tracked during parse via eemeli/yaml).
- Dev mode (`diagnostics: "overlay"`): renders a dismissible overlay listing
  all diagnostics with code frames.
- Prod mode: minimal "config error" block; never blank-screen the host.
- Unknown widget types → render a placeholder widget ("unregistered type: X")
  rather than dropping silently.
- The resolver collects diagnostics for:
  - unknown `widget.type`
  - unknown `action` names (checked against `dispatcher.has()` if provided)
  - duplicate widget `name`
  - grid collisions / overflow
  - use of reserved names (`user-input`, `agent-response`)

---

## 12. Dev Experience

- `agent-ui emit-schema` → writes JSON Schema file. Docs show how to add
  `# yaml-language-server: $schema=./agent-ui.schema.json` for VS Code
  autocomplete.
- `agent-ui validate <file>` → prints diagnostics, exits non-zero on errors.
  Useful in CI.
- Watch mode: when `config` is a URL/path, library re-parses on change
  (dev-only, gated behind `process.env.NODE_ENV !== 'production'`).
- Storybook or a Vite playground for each built-in widget.

---

## 13. Testing Strategy

- **Schema:** fixture-driven. `tests/fixtures/valid/*.yaml` and
  `tests/fixtures/invalid/*.yaml` + expected diagnostic list.
- **Compile:** snapshot test each stage's output
  (`Config → ResolvedConfig → RenderPlan`).
- **Widgets:** React Testing Library with a mock dispatcher that records calls.
- **Layout:** visual regression on representative configs (Playwright
  screenshots — optional for v0.1).
- **Integration:** one end-to-end example app per layout type.

---

## 14. Tech Choices

| Concern        | Pick                               | Note                                                |
|----------------|------------------------------------|-----------------------------------------------------|
| YAML parser    | `yaml` (eemeli/yaml)               | Preserves line/col — better diagnostics than js-yaml|
| Validation     | `ajv` + `ajv-formats`              | JSON Schema runtime; `oneOf` + `const` for widgets  |
| TS types       | `json-schema-to-ts`                | `FromSchema<typeof schema>` infers types compile-time|
| Schema export  | bare JSON Schema (`emitSchema()`)  | For VS Code autocomplete / backend re-use           |
| Build          | `vite` library mode + `tsup`       | ESM + CJS + `.d.ts`                                 |
| Tests          | `vitest` + `@testing-library/react`|                                                     |
| Charts         | defer / `recharts` as peer-dep     | Keep optional                                       |
| Markdown       | `react-markdown`                   | Peer-dep                                            |
| Styling        | Plain CSS + custom properties      | No CSS-in-JS runtime                                |
| Icons          | Host-provided URLs / data URIs     | Don't ship an icon set                              |

---

## 15. Implementation Plan (phased)

Total estimate: **~5–7 weeks** for a solid v0.1, solo.

### Phase 0 — Scaffolding (1–2 days)
- Init package, TS config (strict), Vite library build.
- Vitest + RTL setup.
- ESLint + Prettier.
- CI skeleton (build, test, typecheck).

**Exit:** `npm run build && npm test && npm run typecheck` all green on an empty project.

### Phase 1 — Schema & parse pipeline (3–5 days)
- `yaml` integration with line/col tracking.
- JSON Schemas: `Position`, `Size`, `Action`, `Icon`, `Page`, `MainMenuItem`,
  base `Widget`.
- Fixture runner.
- `Diagnostic` type + Ajv `ErrorObject[]` → Diagnostic mapper.

**Exit:** every fixture parses to either a typed `Config` or an exact
diagnostic list. No widgets yet.

### Phase 2 — Widget registry + resolver (2–3 days)
- `defineWidget()` API with its own JSON Schema per widget (precompiled by Ajv).
- `WidgetRegistry` class (built-ins + extensions).
- `oneOf` union built dynamically from registry.
- Resolver: cross-check `widget.type` against registry; cross-check every
  `action` against `dispatcher.has()` (when provided).

**Exit:** registering a custom widget type works end-to-end in a unit test.

### Phase 3 — Layout engine + planner (3–5 days)
- Grid solver (greedy packer, collision diagnostics).
- Flex / sidebar / tabs compilers.
- Theme resolver (main_color → palette → CSS vars).
- `compile(ResolvedConfig) → RenderPlan` with snapshot tests.

**Exit:** four representative configs (one per `layout_type`) produce stable
`RenderPlan` snapshots.

### Phase 4 — Core render layer (4–6 days)
- `<AgentUI>` entry component.
- Layout roots (`GridRoot`, `FlexRoot`, `SidebarRoot`, `TabsRoot`).
- `<WidgetHost>` wrapper (error boundary, loading skeleton, data binding,
  `useAgentInbox` scoping).
- Default containers (`<UserInput>`, `<AgentResponse>`) with bridge + fallback.
- Diagnostic overlay.
- Base stylesheet + theme tokens.

**Exit:** a minimal example renders with stub widgets.

### Phase 5 — Built-in widgets (5–7 days)
Priority order (each ships with schema + component + story + fixture + test):
1. `markdown` — simplest; validates end-to-end pipeline.
2. `file-type` — validates per-row action menu pattern.
3. `to-do-list-type` — validates write actions + optimistic updates.
4. `data-table`.
5. `form`.
6. `key-value`.
7. `chart` — defer if time tight.

### Phase 6 — Agent bridge (3–5 days)
- `AgentBridge` interface + reference implementation for streaming text.
- Tool-call routing: match `toolCall.widget === widget.name` → targeted inbox.
- `useWidgetData` hook unifying one-shot + subscription.
- `useAgentInbox` hook.

**Exit:** a demo where the agent streams tokens into `agent-response` and
updates a `data-table` widget via a tool call.

### Phase 7 — DX polish (2–3 days)
- CLI: `emit-schema`, `validate`.
- README, API docs, 3 example apps.
- Publish script, changelog template.

### Phase 8 — Beta release (0.1.0)
- Publish to npm under a scoped name.
- Example apps deployed.
- Issue templates, contributing guide.

---

## 16. Success Criteria for v0.1

- A developer can `npm install`, write a 30-line YAML, pass a 10-line
  dispatcher, and get a running UI.
- Breaking the YAML produces a readable overlay with source line numbers.
- VS Code autocomplete works via the emitted JSON Schema.
- Streaming agent output appears in `agent-response` out of the box (when a
  bridge is provided).
- At least one of the example apps is non-trivial (file browser with search +
  download).

---

## 17. Glossary

- **Config** — validated YAML, typed.
- **ResolvedConfig** — config after cross-checks against registry + dispatcher.
- **RenderPlan** — pure data structure consumed by the React layer.
- **Widget** — a typed unit of UI; has a schema, a component, and a `name`.
- **Dispatcher** — host-provided object that resolves action names at runtime.
- **Bridge** — optional host-provided object for streaming agent output into
  containers and tool calls into widgets.
- **Diagnostic** — structured error/warning produced anywhere in the pipeline.

---

## 18. Reference: the user's original example

For quick reference while implementing, the seed example the design is shaped
around is the file/tasks dashboard in §6. It exercises: `layout_type: grid`,
a full `main_menu`, a `file-type` widget with `data_source` + `file_actions`,
and a `to-do-list-type` widget. Phase 5 should make that exact YAML render.
