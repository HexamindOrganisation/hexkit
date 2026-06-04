# agent-ui

A React + TypeScript library that turns a YAML config into a running AI
agent UI, built on shadcn/ui + Tailwind CSS. Everything visible is a widget
— no built-in chrome.

**Full docs:** [docs/README.md](./docs/README.md) ·
[Getting started](./docs/getting-started.md) ·
[Widgets](./docs/widgets.md) ·
[YAML reference](./docs/yaml-reference.md) ·
[Extending](./docs/extending.md)

## Install

```bash
npm install agent-ui react react-dom
npm install -D tailwindcss postcss autoprefixer
```

`tailwind.config.cjs`:

```js
module.exports = {
  presets: [require("agent-ui/tailwind-preset")],
  content: [
    "./src/**/*.{ts,tsx,html}",
    "./node_modules/agent-ui/dist/**/*.{js,cjs}",
  ],
};
```

In your app's CSS entry:

```css
@import "agent-ui/shadcn.css";
@import "agent-ui/style.css";
```

## Quick start

```tsx
import { AgentUI, type ActionDispatcher } from "agent-ui";
import "agent-ui/shadcn.css";
import "agent-ui/style.css";

const dispatcher: ActionDispatcher = {
  async invoke(action, args) {
    if (action === "say_hi") alert("hi");
    return null;
  },
};

const config = `
page:
  layout_type: "grid"

widgets:
  - name: "header"
    type: "page-header"
    size: { width: 12, height: "auto" }
    title: "My Dashboard"

  - name: "actions"
    type: "button-group"
    size: { width: 12, height: "auto" }
    buttons:
      - { label: "Say hi", action: "say_hi" }
`;

export default function App() {
  return <AgentUI config={config} dispatcher={dispatcher} />;
}
```

## Authoring configs in VS Code

```bash
npx agent-ui emit-schema > agent-ui.schema.json
```

Then at the top of your YAML:

```yaml
# yaml-language-server: $schema=./agent-ui.schema.json
```

## CLI

```bash
npx agent-ui validate ./ui.yaml   # exits non-zero on errors
npx agent-ui emit-schema          # prints JSON Schema
```

## Architecture

1. **parse** YAML → data + source map
2. **validate** with JSON Schema (Ajv) — `oneOf` + `const` discriminator per widget type
3. **resolve** against the widget registry + dispatcher
4. **normalize** defaults
5. **compile** layout math → `RenderPlan`
6. **render** as React
7. **runtime** dispatches actions, subscribes to agent streams, maintains the conversation log

Stages 1–5 are pure and return `Result<T, Diagnostic[]>`. The `RenderPlan` is
serializable and snapshot-testable.

## Built-in widgets

| `type`           | Purpose                                       |
|------------------|-----------------------------------------------|
| `page-header`    | Title + optional subtitle/icon                |
| `page-footer`    | Single-line footer                            |
| `button-group`   | Row/column of action buttons (shadcn)         |
| `ai-chat-input`  | Textarea + send → `AgentBridge`               |
| `ai-response`    | Live chat transcript (user + agent + tokens)  |
| `spacer`         | Empty cell — reserves layout space            |
| `markdown`       | Renders markdown text safely (no HTML / no JS execution) |
| `form`           | Schema-driven form → dispatcher action        |
| `metrics`        | Strip of stat cards bound to a data source    |
| `table`          | Scrollable CSV table (head/tail rows)         |
| `tool-calls`     | Live log of agent tool invocations            |

See [docs/widgets.md](./docs/widgets.md) for each widget's YAML schema and
behavior.

## Examples

Three runnable examples live under [`examples/`](./examples):

- [`examples/minimal`](./examples/minimal) — native widgets driven by a
  mock dispatcher and echo agent. No server needed.
- [`examples/llm`](./examples/llm) — same UI wired to a small FastAPI
  backend with an OpenAI-backed `/chat` endpoint and persisted
  conversations.
- [`examples/layouts`](./examples/layouts) — the same five widgets rendered
  under both `layout_type`s (`grid`, `flex`) with a top-bar switcher.

```bash
npm install
npm run example          # examples/minimal       (port 5173)
npm run example:llm      # examples/llm           (port 5174 — start backend first)
npm run example:layouts  # examples/layouts       (port 5175)
```

## Custom widgets

```tsx
import {
  defineWidget,
  WidgetRegistry,
  builtinWidgets,
  WidgetBaseProperties,
} from "agent-ui";
import type { FromSchema } from "json-schema-to-ts";

const BannerSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "banner" },
    message: { type: "string" },
  },
  required: ["name", "type", "size", "message"],
  additionalProperties: false,
} as const;

type BannerProps = FromSchema<typeof BannerSchema>;

const banner = defineWidget<BannerProps>({
  type: "banner",
  schema: BannerSchema,
  component: ({ props }) => (
    <div className="rounded-md bg-accent px-4 py-2 text-accent-foreground">
      {props.message}
    </div>
  ),
});

const widgets = new WidgetRegistry([...builtinWidgets, banner]);

<AgentUI config={cfg} dispatcher={d} widgets={widgets} />
```

## Agent streaming (optional)

```ts
import type { AgentBridge } from "agent-ui";

const agent: AgentBridge = {
  async onUserSubmit(text) { /* kick off a turn */ },
  subscribeAgentOutput(cb) {
    // emit { kind: "token", text, messageId? } |
    //      { kind: "message", role, content, messageId? } |
    //      { kind: "status", state: "idle" | "thinking" | "responding" } |
    //      { kind: "tool-call", widget, payload } |
    //      { kind: "error", message }
    return () => { /* unsubscribe */ };
  },
};

<AgentUI config={cfg} dispatcher={d} agent={agent} />
```

`tool-call` events must include a `widget` field. They route to exactly that
widget — no broadcast, no fallback. Widgets read their inbox via:

```ts
const { lastPayload, history } = useAgentInbox<MyShape>();
```

The full conversation (user + assistant + system) is also exposed:

```ts
const { messages } = useConversation();
```

## License

MIT
