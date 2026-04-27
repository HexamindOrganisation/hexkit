# Extending agent-ui

How to plug in your own widget types, theme tokens, and agent behavior.

## Custom widgets

Three things make a widget:

1. A **Zod schema** for its YAML shape.
2. A **React component** that receives the validated props.
3. A call to `defineWidget` to bind them.

Register the result in a `WidgetRegistry` and pass it to `<AgentUI>`.

```tsx
import { z } from "zod";
import {
  defineWidget,
  WidgetRegistry,
  builtinWidgets,
  AgentUI,
  WidgetBaseShape,
  type WidgetProps,
} from "agent-ui";

const BannerSchema = z.object({
  ...WidgetBaseShape,                       // name, type, position, size, tab
  type: z.literal("banner"),
  message: z.string(),
  tone: z.enum(["info", "warn", "error"]).default("info"),
});

type BannerProps = z.infer<typeof BannerSchema>;

function Banner({ props }: WidgetProps<BannerProps>) {
  // Tailwind classes work because the consumer's tailwind.config includes
  // node_modules/agent-ui/dist (and your own source) in `content`.
  return (
    <div
      className={
        props.tone === "error"
          ? "rounded-md bg-destructive px-4 py-2 text-destructive-foreground"
          : props.tone === "warn"
            ? "rounded-md bg-yellow-100 px-4 py-2 text-yellow-900"
            : "rounded-md bg-accent px-4 py-2 text-accent-foreground"
      }
    >
      {props.message}
    </div>
  );
}

const banner = defineWidget({
  type: "banner",
  schema: BannerSchema,
  component: Banner,
});

const registry = new WidgetRegistry([...builtinWidgets, banner]);

export function App() {
  return <AgentUI config={yaml} dispatcher={dispatcher} widgets={registry} />;
}
```

Now `type: "banner"` works in YAML:

```yaml
- name: "hero"
  type: "banner"
  size: { width: 12, height: "auto" }
  message: "System maintenance tonight at 10pm."
  tone: "warn"
```

### `chromeless` widgets

If your widget should sit flush (no border/padding from the default
`<div class="au-widget-host">`), pass `chromeless: true`:

```ts
defineWidget({
  type: "banner",
  schema: BannerSchema,
  component: Banner,
  chromeless: true,
});
```

This is what the built-in `page-header`, `page-footer`, `ai-chat-input`,
`ai-response`, and `ai-history` widgets do.

### Footer-slot widgets

Pass `slot: "footer"` to render the widget outside the layout, pinned to
the bottom of the page:

```ts
defineWidget({
  type: "status-bar",
  schema: StatusBarSchema,
  component: StatusBar,
  chromeless: true,
  slot: "footer",
});
```

Footer-slot widgets:

- Are **excluded** from the layout (`grid` / `flex` / `sidebar` / `tabs`).
- Honor neither `position` nor `size.width` — they always span the full
  page width.
- Are stacked in YAML order in a single footer area pinned to the bottom of
  the AgentUI shell.

This is what the built-in `page-footer` widget does.

### Replacing a built-in

Pass your version *after* `builtinWidgets` — later registrations win. For
example, a custom file-tree:

```tsx
import { FileTreeWidgetSchema, defineWidget } from "agent-ui";

const fancyFileTree = defineWidget({
  type: "file-tree",                  // same type → overrides the built-in
  schema: FileTreeWidgetSchema,
  component: MyFancyFileTree,
});

const registry = new WidgetRegistry([...builtinWidgets, fancyFileTree]);
```

### Widget defaults

```ts
defineWidget({
  type: "banner",
  schema: BannerSchema,
  defaults: { tone: "info" },         // shallow-merged into raw YAML before validation
  component: Banner,
});
```

User-set fields still win.

## Widget runtime hooks

Widgets receive `props` and `dispatcher` directly. For everything else, use
hooks.

### `useWidgetData<T>(dataSource)`

Reads data from a `data_source` subtree in the widget's YAML. Transparently
uses `dispatcher.subscribe` when available (with `subscribe: true` in the
YAML) or falls back to a one-shot `invoke`.

```tsx
import { useWidgetData } from "agent-ui";

function MyWidget({ props }: WidgetProps<MySchema>) {
  const { data, loading, error } = useWidgetData<Row[]>(props.data_source);
  if (error) return <div>Error: {error.message}</div>;
  if (loading && !data) return <div>Loading…</div>;
  return <table>…</table>;
}
```

### `useAgentInbox<T>()`

Returns the latest `tool-call.payload` routed to **this** widget by name,
plus its history. Isolation-safe: a widget can only read its own inbox.

```tsx
import { useAgentInbox } from "agent-ui";

function ActivityFeed() {
  const { lastPayload, history } = useAgentInbox<Event>();
  return <ul>{history.map((e, i) => <li key={i}>{e.kind}</li>)}</ul>;
}
```

A widget called `"feed"` receives an event like:

```ts
emit({ kind: "tool-call", widget: "feed", payload: { kind: "heartbeat" } });
```

If `widget` doesn't match any widget `name` in the plan, the event drops
with a diagnostic — no broadcast.

### `useConversation()`

Reads the full conversation log (user + assistant + system, finalized only).
The same log that backs the built-in `ai-history` widget.

```tsx
import { useConversation, type ConversationMessage } from "agent-ui";

function MyHistory() {
  const { messages } = useConversation();
  return (
    <ul>
      {messages.map((m: ConversationMessage) => (
        <li key={m.id}>
          [{m.role}] {m.content}
        </li>
      ))}
    </ul>
  );
}
```

User messages land here when the user submits via `ai-chat-input` (or any
widget that calls `useAgentUIContext().pushUserMessage(text)`). Assistant
messages land here from finalized `message` events on the `AgentBridge`.

### `useAgentUIContext()`

Escape hatch for the full provider value: `{ dispatcher, agent,
pushUserMessage, pushDiagnostic, conversation, ... }`. Useful when building
custom widgets that need fine-grained control.

## Dispatcher patterns

### Routing to multiple backends

```ts
const dispatcher: ActionDispatcher = {
  async invoke(action, args) {
    if (action.startsWith("db.")) return callDb(action, args);
    if (action.startsWith("file.")) return callFiles(action, args);
    if (action.startsWith("ai.")) return callClaude(action, args);
    throw new Error(`unknown action: ${action}`);
  },
  has(action) {
    return /^(db|file|ai)\./.test(action);
  },
};
```

### Subscription (streaming data)

```ts
const dispatcher: ActionDispatcher = {
  async invoke(action, args) { /* ... */ },
  subscribe(action, args, onData) {
    const es = new EventSource(`/stream?action=${action}`);
    es.onmessage = (e) => onData(JSON.parse(e.data));
    return () => es.close();
  },
};
```

And in YAML:

```yaml
- name: "Files"
  type: "file-tree"
  data_source:
    action: "watch.files"
    subscribe: true
  size: { width: 12, height: "auto" }
```

### Routing through Claude tool use

```ts
import Anthropic from "@anthropic-ai/sdk";
const client = new Anthropic();

const dispatcher: ActionDispatcher = {
  async invoke(action, args) {
    const res = await client.messages.create({
      model: "claude-opus-4-7",
      max_tokens: 1024,
      tools: [ /* your tool definitions, keyed by action name */ ],
      messages: [{ role: "user", content: `Run ${action} with ${JSON.stringify(args)}` }],
    });
    return extractToolResult(res);
  },
};
```

## AgentBridge patterns

### Connecting to a backend stream

```ts
const agent: AgentBridge = {
  async onUserSubmit(text) {
    await fetch("/api/chat", { method: "POST", body: JSON.stringify({ text }) });
  },
  subscribeAgentOutput(emit) {
    const es = new EventSource("/api/chat/stream");
    es.addEventListener("token",   (e) => emit({ kind: "token",    ...JSON.parse(e.data) }));
    es.addEventListener("message", (e) => emit({ kind: "message",  ...JSON.parse(e.data) }));
    es.addEventListener("tool",    (e) => emit({ kind: "tool-call",...JSON.parse(e.data) }));
    es.addEventListener("status",  (e) => emit({ kind: "status",   ...JSON.parse(e.data) }));
    return () => es.close();
  },
};
```

### Driving widgets from the agent

A typical flow: user asks a question, the agent calls a tool that returns
structured data, and you push that data into a specific widget:

```ts
// Server-side pseudocode
onToolResult("list_user_files", (result) => {
  emit({ kind: "tool-call", widget: "Files", payload: result.files });
});
```

The widget named `"Files"` reads `useAgentInbox` internally:

```tsx
function FileTreeWidget({ props }) {
  const { data } = useWidgetData(props.data_source);
  const { lastPayload } = useAgentInbox();
  const nodes = lastPayload ?? data ?? props.nodes ?? [];
  // agent updates win over the data-source fetch, which wins over static nodes
}
```

That's exactly what the built-in `file-tree` widget does.

## Theming

There are two layers: the **shadcn/Tailwind** layer (used by the built-in
widgets) and the **legacy CSS variables** (used by the structural shell:
sidebar layout, tabs, widget host frame, diagnostics overlay).

### shadcn / Tailwind

Edit the CSS variables in your own globals after importing `agent-ui/shadcn.css`:

```css
@import "agent-ui/shadcn.css";

:root {
  --primary: 280 75% 52%;            /* purple */
  --radius: 0.75rem;
}
```

The variables match the canonical shadcn palette — see
[shadcn.css](../src/shadcn.css) for the full list. Set the `.dark` class on
a parent to flip into dark mode.

You can also extend the Tailwind preset in your own `tailwind.config.cjs`:

```js
module.exports = {
  presets: [require("agent-ui/tailwind-preset")],
  content: ["./src/**/*.{ts,tsx}", "./node_modules/agent-ui/dist/**/*.{js,cjs}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
    },
  },
};
```

### Constrained theme API — mode + accent + escape hatch

The theme is intentionally minimal. Both `<AgentUI theme={...}>` and the
YAML `page.theme` block accept the same shape:

```ts
interface ThemeTokens {
  mode?: "light" | "dark" | "system";
  accent?: string;                    // hex
  overrides?: Record<string, string>; // raw CSS-var values
}
```

```tsx
<AgentUI
  config={yaml}
  dispatcher={dispatcher}
  theme={{
    mode: "dark",
    accent: "#8b5cf6",
  }}
/>
```

**Why so few knobs?** shadcn ships ~15 interrelated CSS variables tuned to
work together at specific lightness levels for each mode. Letting users
pick arbitrary `background` and `foreground` hex values (the previous
API) was a foot-gun: text contrast got weird, borders disappeared, muted
sections didn't read as muted. The current API picks a curated palette
*as a whole* via `mode`, then lets you re-color the brand surface with
one `accent` value.

**What `accent` bridges to:**

| Resolved CSS variable    | Source        |
|--------------------------|---------------|
| `--primary`              | `accent` (HSL) |
| `--ring`                 | `accent` (HSL) — focus rings |
| `--primary-foreground`   | auto-contrast over `accent` |

Everything else (`--background`, `--foreground`, `--card`, `--popover`,
`--muted`, `--accent`, `--secondary`, `--destructive`, `--border`,
`--input`, …) stays at the value defined in `agent-ui/shadcn.css` for the
active mode.

**`mode: "system"`** tracks `prefers-color-scheme` at runtime. The shell
listens to the media query and toggles a `dark` class on the AgentUI root,
which flips the palette via the `.dark` selector in `agent-ui/shadcn.css`.

**Escape hatch — `overrides`.** When a curated default really doesn't fit,
write the variable directly:

```tsx
<AgentUI
  theme={{
    mode: "light",
    accent: "#4F46E5",
    overrides: {
      "--muted": "210 40% 90%",
      "--border": "214 32% 88%",
      "--radius": "0.75rem",
    },
  }}
/>
```

Values are written verbatim as inline CSS on the AgentUI root. For shadcn
vars, pass HSL triplets like `"210 40% 90%"` (they're consumed via
`hsl(var(...))`). Reach for this only when you need it.

### Legacy `--au-*` tokens

The structural shell (`.au-root`, `.au-sidebar`, `.au-tab-bar`,
`.au-diagnostics`, etc.) uses a small set of legacy custom properties
internally. They're now derived from the shadcn palette:

```css
.au-root {
  --au-bg: hsl(var(--background));
  --au-fg: hsl(var(--foreground));
  --au-accent: hsl(var(--primary));
  --au-accent-fg: hsl(var(--primary-foreground));
  --au-border: hsl(var(--border));
  --au-radius: var(--radius);
  --au-accent-soft: hsl(var(--primary) / 0.1);
  /* + --au-space-1..6 (spacing scale) */
}
```

So the legacy chrome automatically follows light/dark mode and the
user's accent — there's nothing to configure separately.

### Per-widget styling

Every widget is wrapped in `<div class="au-widget-host" data-widget-name="…"
data-widget-type="…">`, so scoped CSS is easy:

```css
.au-widget-host[data-widget-type="file-tree"] {
  background: #fafafa;
}
.au-widget-host[data-widget-name="Quick actions"] {
  /* ... */
}
```

Chromeless widgets get the additional class `au-widget-host-chromeless`.

## Working with the plan directly

The compile pipeline is exported for advanced use:

```ts
import { parseYaml, compilePlan, WidgetRegistry, builtinWidgets } from "agent-ui";

const parsed = parseYaml(yamlText);
if (!parsed.ok) return parsed.errors;

const plan = compilePlan(parsed.value.data, {
  registry: new WidgetRegistry(builtinWidgets),
  locate: parsed.value.locate,
});
if (!plan.ok) return plan.errors;

// plan.value is a RenderPlan: serializable, snapshot-testable.
console.log(plan.value.layout);
console.log(plan.value.widgets);
```

Good for:

- Snapshot tests that pin the shape of your layout.
- Prerendering / SSR where you want to inspect a plan before mounting.
- Building a visual editor on top.

## Testing

The library doesn't ship a test harness, but the pieces compose well:

```ts
import { compilePlan, WidgetRegistry, builtinWidgets } from "agent-ui";

test("dashboard has a header and a button group", () => {
  const config = {
    page: { layout_type: "grid" },
    widgets: [
      {
        name: "header",
        type: "page-header",
        size: { width: 12, height: "auto" },
        title: "Hi",
      },
      {
        name: "actions",
        type: "button-group",
        size: { width: 12, height: "auto" },
        buttons: [{ label: "Go", action: "go" }],
      },
    ],
  };
  const plan = compilePlan(config, { registry: new WidgetRegistry(builtinWidgets) });
  expect(plan.ok).toBe(true);
  if (!plan.ok) return;
  expect(plan.value.widgets).toHaveLength(2);
});
```

Mock dispatchers are also straightforward:

```ts
const calls: [string, unknown][] = [];
const dispatcher: ActionDispatcher = {
  async invoke(a, args) { calls.push([a, args]); return null; },
};
```

## Importing internals

The public surface is deliberately narrow; here's what's exported:

- **Mount**: `AgentUI`, `AgentUIProps`
- **Runtime**: `ActionDispatcher`, `nullDispatcher`, `AgentBridge`, `AgentEvent`
- **Registry**: `defineWidget`, `WidgetRegistry`, `builtinWidgets`, `WidgetDefinition`, `AnyWidgetDefinition`, `WidgetProps`
- **Hooks**: `useWidgetData`, `useAgentInbox`, `useAgentUIContext`, `useConversation`, `ConversationMessage`
- **Schema**: `ConfigSchema`, `buildConfigSchema`, `BuiltinWidgetSchemas`, `BuiltinWidgetType`, `BuiltinWidget`, `WidgetBaseShape`, `WidgetBaseSchema`, plus per-widget schemas (`PageHeaderWidgetSchema`, `FileTreeWidgetSchema`, …) and types
- **Compile**: `parseYaml`, `compilePlan`, `resolve`, `normalize`, `resolveTheme`, `RenderPlan`, `RenderPlanWidget`, `ResolvedConfig`, `ResolvedWidget`, `ResolvedTheme`, `ThemeTokens`, `ParseResult`, `SourceMap`
- **Diagnostics**: `Diagnostic`, `DiagnosticSeverity`, `Result`

If you need something else, file an issue — the surface is intentionally
held small.
