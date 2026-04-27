# Getting started

`agent-ui` renders a React UI from a YAML file. You write the layout +
widgets in YAML, the library loads it, validates it, and mounts an
`<AgentUI>` component. Everything visible is a widget — there is no built-in
header, footer, or chat shell.

## Install

```bash
npm install agent-ui react react-dom
```

The library uses **shadcn/ui + Tailwind CSS** for the built-in widgets. You
must install Tailwind in your app and apply the bundled preset.

```bash
npm install -D tailwindcss postcss autoprefixer
```

`tailwind.config.cjs`:

```js
const path = require("node:path");

module.exports = {
  presets: [require("agent-ui/tailwind-preset")],
  content: [
    "./src/**/*.{ts,tsx,html}",
    // Important: include the library's compiled output so its Tailwind classes are picked up.
    "./node_modules/agent-ui/dist/**/*.{js,cjs}",
  ],
};
```

`postcss.config.cjs`:

```js
module.exports = {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

In your app's CSS entry:

```css
@import "agent-ui/shadcn.css";   /* Tailwind directives + shadcn CSS variables */
@import "agent-ui/style.css";    /* structural shell, layout chrome, diagnostics */
```

You also need a way to read YAML as text. With Vite the idiomatic form is
`import configText from "./ui.yaml?raw"`. With other bundlers, read the YAML
however you prefer and pass the string (or a parsed object) to `<AgentUI>`.

## Minimum working example

```tsx
import { AgentUI, type ActionDispatcher } from "agent-ui";
import "agent-ui/shadcn.css";
import "agent-ui/style.css";

const yaml = `
page:
  layout_type: "grid"
widgets:
  - name: "header"
    type: "page-header"
    size: { width: 12, height: "auto" }
    title: "Hello"
    subtitle: "from agent-ui"
  - name: "actions"
    type: "button-group"
    size: { width: 12, height: "auto" }
    buttons:
      - { label: "Click me", action: "say_hi" }
`;

const dispatcher: ActionDispatcher = {
  async invoke(action) {
    if (action === "say_hi") alert("hi");
    return null;
  },
};

export default function App() {
  return <AgentUI config={yaml} dispatcher={dispatcher} />;
}
```

## The `<AgentUI>` component

```ts
interface AgentUIProps {
  config: string | object | URL;     // raw YAML, already-parsed object, or fetchable
  dispatcher: ActionDispatcher;      // required — see Dispatcher
  widgets?: WidgetRegistry | AnyWidgetDefinition[];  // extend built-in widgets
  agent?: AgentBridge;               // optional — for streaming agent output
  theme?: Partial<ThemeTokens>;      // override structural-shell theme tokens
  diagnostics?: "overlay" | "console" | "silent";   // default: "overlay"
  onError?: (diagnostics: Diagnostic[]) => void;
}
```

- If `config` is a **string with a newline** or with `something:`, it's
  treated as raw YAML. Any other string is fetched as a URL.
- If `config` is an **object**, YAML parsing is skipped. Useful for
  dynamically-generated configs and tests.
- If `config` is a **`URL`**, the library fetches and parses it.

## Dispatcher

The dispatcher is the only way widgets talk to your application. Every
`action:` string in the YAML is a name you control — a widget calls
`dispatcher.invoke("the-name", args)` and you decide what that means.

```ts
interface ActionDispatcher {
  invoke(action: string, args?: unknown): Promise<unknown>;
  subscribe?(
    action: string,
    args: unknown,
    onData: (d: unknown) => void,
    onError?: (e: unknown) => void,
  ): () => void;
  has?(action: string): boolean;
}
```

Minimal example:

```ts
const dispatcher: ActionDispatcher = {
  async invoke(action, args) {
    switch (action) {
      case "list_files": return await fetch("/api/files").then(r => r.json());
      case "save":       return await fetch("/api/save", { method: "POST", body: JSON.stringify(args) });
      default:           return null;
    }
  },
  // Optional: lets the resolver warn about YAML actions you haven't wired up.
  has(action) {
    return ["list_files", "save"].includes(action);
  },
};
```

**When each method is called:**

| Method | When |
|---|---|
| `invoke` | Widget mounts with `data_source`; button-group click; file-tree action click; ai-chat-input fallback when no AgentBridge |
| `subscribe` | Widget has `data_source: { ..., subscribe: true }` — for streaming data |
| `has` | At resolve time, to emit warnings for unknown actions |

## AgentBridge (optional)

Opt in when your UI shows streaming output from an AI agent.

```ts
interface AgentBridge {
  onUserSubmit: (text: string) => void | Promise<void>;
  subscribeAgentOutput: (cb: (event: AgentEvent) => void) => () => void;
}

type AgentEvent =
  | { kind: "token";     text: string; messageId?: string }
  | { kind: "message";   role: "assistant" | "system"; content: string; messageId?: string }
  | { kind: "status";    state: "idle" | "thinking" | "responding" }
  | { kind: "tool-call"; widget: string; payload: unknown }
  | { kind: "error";     message: string };
```

Example that mocks a streaming turn:

```ts
const agent: AgentBridge = {
  onUserSubmit(text) {
    console.log("User said:", text);
  },
  subscribeAgentOutput(emit) {
    const id = "m1";
    emit({ kind: "status", state: "responding" });
    const chunks = ["Hello ", "there ", "— let me think."];
    const timers = chunks.map((text, i) =>
      setTimeout(() => emit({ kind: "token", text, messageId: id }), 200 * (i + 1)),
    );
    const final = setTimeout(() => {
      emit({ kind: "message", role: "assistant", content: "Hello there — let me think.", messageId: id });
      emit({ kind: "status", state: "idle" });
    }, 200 * (chunks.length + 1));
    return () => {
      timers.forEach(clearTimeout);
      clearTimeout(final);
    };
  },
};
```

### Event routing

| Event kind | Goes to |
|---|---|
| `token` | `ai-response` widget(s), coalesced by `messageId` into one growing bubble. |
| `message` | `ai-response` widget(s) (finalized bubble) **and** the conversation log read by `ai-history`. |
| `status` | `ai-response` widget(s) ("…thinking" / "…responding" indicator). |
| `tool-call` | **Exactly one** widget: the one whose `name === event.widget`. No broadcast. |
| `error` | `ai-response` widget(s), conversation log (as a system message), and the diagnostics overlay. |

`tool-call.widget` is **required**. Events with no widget name, or a name
that doesn't match any widget in the plan, are dropped with a dev-mode
warning. This is how widget isolation is preserved.

If your config has no `ai-response` widget, the agent's streaming output is
still tracked in the conversation log (visible via `ai-history` or
`useConversation()`) but isn't displayed by a streaming bubble.

### No bridge? Fallbacks

- **`ai-chat-input`**: if `dispatcher.has("user-submit")` is true, submits
  fall back to `dispatcher.invoke("user-submit", { text })`. Otherwise the
  textarea renders inert with a dev warning. The user message still lands in
  the conversation log either way.
- **`ai-response`**: shows `empty_text` (or "No agent bridge connected.").
- **`ai-history`**: shows whatever's in the log — initially empty.
- **`tool-call`** events: unreachable. Widgets that expect agent updates
  simply won't receive any, but they can still load via `data_source`.

## Conversation log

The provider maintains a unified conversation log:

```ts
import { useConversation } from "agent-ui";

const { messages } = useConversation();
// messages: { id, role: "user" | "assistant" | "system", content, timestamp }[]
```

It's populated by `ai-chat-input` (user submits) and by the provider's
`AgentBridge` subscription (assistant `message` events and `error` events).
The `ai-history` widget reads from this log. Token-only streams without a
closing `message` event do **not** appear here — emit a `message` to mark a
turn complete.

## Diagnostics

The library validates everything before rendering. Errors don't crash the
host — they surface in one of three ways, controlled by the `diagnostics`
prop:

- `"overlay"` *(default)*: dismissible floating panel in the corner with
  line-numbered errors.
- `"console"`: log to `console.error` / `console.warn`, no UI.
- `"silent"`: suppress all reporting — your `onError` callback is your only
  signal.

Diagnostics include YAML source `line` and `col` when available.

## CLI

The library ships a bin:

```bash
npx agent-ui emit-schema > agent-ui.schema.json
```

Emits a JSON Schema for your YAML. Add this to the top of your YAML for full
autocomplete in VS Code:

```yaml
# yaml-language-server: $schema=./agent-ui.schema.json
```

```bash
npx agent-ui validate ./ui.yaml
```

Validates a config and exits non-zero on errors. Good for CI.

## Next steps

- **[YAML reference](./yaml-reference.md)** — config shape, layouts, and diagnostics.
- **[Widgets](./widgets.md)** — every native widget's YAML schema and behavior.
- **[Extending](./extending.md)** — custom widgets, custom dispatchers, hooks.
