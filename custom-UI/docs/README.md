# agent-ui · documentation

Four documents, ordered by depth:

- **[Getting started](./getting-started.md)** — install, Tailwind preset
  setup, the minimum working example, the `<AgentUI>` props, the
  `ActionDispatcher` and `AgentBridge` contracts, event routing, the
  conversation log, diagnostics, and the CLI.

- **[Widgets](./widgets.md)** — every native widget's YAML schema, runtime
  behavior, and resolution order. The reference for *what* you can put in
  your config's `widgets:` array.

- **[YAML reference](./yaml-reference.md)** — the *shape* of a config:
  top-level keys, `page` settings, common widget envelope fields, layouts,
  the shared `data_source` sub-schema, and diagnostics codes.

- **[Extending](./extending.md)** — custom widget registration, the
  `chromeless` flag, runtime hooks (`useWidgetData`, `useAgentInbox`,
  `useConversation`, `useAgentUIContext`), dispatcher and `AgentBridge`
  patterns, theming via shadcn variables and the legacy structural tokens,
  and the public surface.

## The one-minute overview

You write a YAML file that describes a page and a flat list of widgets.
Everything visible is a widget — no built-in header, footer, or chat shell:

```yaml
page:
  layout_type: "grid"

widgets:
  - name: "header"
    type: "page-header"
    size: { width: 12, height: "auto" }
    title: "My Dashboard"

  - name: "Files"
    type: "file-tree"
    size: { width: 6, height: 400 }
    data_source: { action: "list_user_files" }
    on_select: "open_file"

  - name: "chat-input"
    type: "ai-chat-input"
    size: { width: 12, height: "auto" }

  - name: "agent-output"
    type: "ai-response"
    size: { width: 12, height: "auto" }
```

You mount `<AgentUI>` with that YAML, an `ActionDispatcher` (how actions
map to real work), and optionally an `AgentBridge` (how streaming agent
output flows into the UI):

```tsx
<AgentUI config={yamlText} dispatcher={dispatcher} agent={agent} />
```

The library parses, validates, compiles, and renders.

## Mental model

```
YAML → parse → validate → resolve → normalize → compile → RenderPlan → React
                    ↑            ↑
           (widget registry)  (dispatcher.has for warnings)
```

Stages 1–5 are pure. The `RenderPlan` is a serializable intermediate —
testable, diffable, and the boundary where hot reload would hook in. Stage 6
is the React tree. Stage 7 is runtime: the dispatcher handles actions, the
optional bridge streams `token` / `message` / `status` / `tool-call` /
`error` events, and the provider maintains a conversation log readable via
`useConversation()`.

## Quick links by question

| If you want to… | Read |
|---|---|
| Install and ship a "hello world" | [Getting started](./getting-started.md) |
| Configure a `file-tree` or `ai-chat-input` | [Widgets](./widgets.md) |
| Understand layouts (`grid`, `flex`, `sidebar`, `tabs`) | [YAML reference — Layouts](./yaml-reference.md#layouts) |
| Add a custom widget type | [Extending — Custom widgets](./extending.md#custom-widgets) |
| Read the conversation log from your code | [Extending — useConversation](./extending.md#useconversation) |
| Style with shadcn / Tailwind | [Extending — Theming](./extending.md#theming) |
| Wire `<AgentUI>` to a streaming AI agent | [Getting started — AgentBridge](./getting-started.md#agentbridge-optional) |
| Validate configs in CI | [Getting started — CLI](./getting-started.md#cli) |
| Look up a diagnostic code | [YAML reference — Diagnostics codes](./yaml-reference.md#diagnostics-codes) |

## Examples in this repo

Three runnable examples live under [`examples/`](../examples):

- [`examples/minimal`](../examples/minimal) — the native widgets driven
  by a **mock dispatcher and echo agent**. No server needed.
- [`examples/llm`](../examples/llm) — same UI wired to a small **FastAPI
  backend** with an OpenAI-backed `/chat` endpoint, persisted
  conversations, and a live `metrics` strip (requests / tokens / cost /
  last-request latency) sourced from `/metrics`. See
  [`examples/llm/backend/README.md`](../examples/llm/backend/README.md)
  for setup.
- [`examples/layouts`](../examples/layouts) — the **same five widgets**
  (`page-header`, `markdown`, `form`, `button-group`, `page-footer`)
  rendered under all four `layout_type`s (`grid`, `flex`, `sidebar`,
  `tabs`). One React app, four YAML configs, a top-bar switcher. Stub
  dispatcher logs every action to the console — no backend.

Run them:

```bash
npm install
npm run example          # mock — examples/minimal       (port 5173)
npm run example:llm      # backend-wired — examples/llm  (port 5174,
                         # start the FastAPI server first, see its README)
npm run example:layouts  # layout showcase — examples/layouts (port 5175)
```
