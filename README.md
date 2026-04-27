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
    if (action === "list_user_files") return await fetch("/api/files").then(r => r.json());
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

  - name: "Files"
    type: "file-tree"
    size: { width: 12, height: 400 }
    data_source: { action: "list_user_files" }
    on_select: "open_file"
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
2. **validate** with Zod discriminated unions
3. **resolve** against the widget registry + dispatcher
4. **normalize** defaults
5. **compile** layout math → `RenderPlan`
6. **render** as React
7. **runtime** dispatches actions, subscribes to agent streams, maintains the conversation log

Stages 1–5 are pure and return `Result<T, Diagnostic[]>`. The `RenderPlan` is
serializable and snapshot-testable.

## Built-in widgets

| `type`           | Purpose                                 |
|------------------|-----------------------------------------|
| `page-header`    | Title + optional subtitle/icon          |
| `page-footer`    | Single-line footer                      |
| `button-group`   | Row/column of action buttons (shadcn)   |
| `file-tree`      | Recursive folder/file tree              |
| `ai-chat-input`  | Textarea + send → AgentBridge           |
| `ai-response`    | Streaming agent output (tokens + msgs)  |
| `ai-history`     | Full conversation transcript            |

See [docs/widgets.md](./docs/widgets.md) for each widget's YAML schema and
behavior.

## Custom widgets

```tsx
import { defineWidget, WidgetRegistry, builtinWidgets, WidgetBaseShape } from "agent-ui";
import { z } from "zod";

const banner = defineWidget({
  type: "banner",
  schema: z.object({
    ...WidgetBaseShape,
    type: z.literal("banner"),
    message: z.string(),
  }),
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
    // emit { kind: "token", text } | { kind: "message", role, content } |
    //      { kind: "status", state } | { kind: "tool-call", widget, payload } |
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
