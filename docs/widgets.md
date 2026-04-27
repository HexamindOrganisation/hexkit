# Configuring widgets

Every visible thing in an agent-ui page is a widget. There is no special header,
footer, or chat container shell — they are all widgets you place via the
`widgets:` array in YAML.

This page documents every native widget: its `type`, its YAML schema, what it
renders, and what runtime hooks it consumes.

For the *envelope* every widget shares (`name`, `position`, `size`, `tab`),
see [yaml-reference.md](./yaml-reference.md#common-widget-fields). For
custom widgets, see [extending.md](./extending.md).

## Widget catalog

| `type`           | Purpose                              | Chromeless |
|------------------|--------------------------------------|------------|
| `page-header`    | Title + optional subtitle/icon       | yes        |
| `page-footer`    | Single-line footer                   | yes        |
| `button-group`   | Row/column of action buttons         | no         |
| `file-tree`      | Recursive folder/file tree           | no         |
| `ai-chat-input`  | Textarea + send → AgentBridge        | yes        |
| `ai-response`    | Streaming agent output (tokens + msg)| yes        |
| `ai-history`     | Full conversation transcript         | yes        |

**Chromeless** widgets opt out of the default `<div class="au-widget-host">`
border/padding so they sit flush with the page edges.

---

## `page-header`

A title row at the top of a layout. The successor to the old hardcoded page
chrome — you place it as a widget so layouts that don't want a header can
simply omit it.

### YAML

```yaml
- name: "header"
  type: "page-header"
  position: { horizontal: "left", vertical: "high" }
  size: { width: 12, height: "auto" }
  title: "My Dashboard"        # required, non-empty
  subtitle: "Internal tools"   # optional
  icon: "/assets/logo.svg"     # optional; URL or data URI
```

### Renders

A `<header>` with the icon (if any) on the left, then a stacked `title` /
`subtitle` block. Styled with shadcn tokens: `bg-background`,
`border-b border-border`, foreground/muted text.

### Tips

- Pair with a `button-group` at the same `vertical: "high"` row to get a
  header + actions bar — the grid packer places them side-by-side.
- Set `size: { width: 12, height: "auto" }` to span the full row.

---

## `page-footer`

A single-line footer. Same role as `page-header` but at the bottom.

### YAML

```yaml
- name: "footer"
  type: "page-footer"
  position: { horizontal: "left", vertical: "low" }
  size: { width: 12, height: "auto" }
  text: "© 2026 ACME · v1.2.0"   # optional
```

### Renders

A `<footer>` centered text band, muted foreground, top border. If `text` is
omitted, an empty footer band still renders (useful as a spacer).

---

## `button-group`

A row (or column) of shadcn buttons. Each click invokes a dispatcher action.

### YAML

```yaml
- name: "Quick actions"
  type: "button-group"
  position: { horizontal: "left", vertical: "high" }
  size: { width: 12, height: "auto" }
  orientation: "horizontal"   # optional; "horizontal" (default) or "vertical"
  buttons:                    # required; at least 1
    - label: "Refresh"
      action: "refresh_data"
      variant: "default"      # optional; default | destructive | outline | secondary | ghost | link
      size: "default"         # optional; default | sm | lg | icon
      disabled: false         # optional
      args:                   # optional; passed as the second arg to dispatcher.invoke()
        scope: "all"
    - label: "Settings"
      action: "open_settings"
      variant: "outline"
    - label: "Delete all"
      action: "delete_all"
      variant: "destructive"
```

### Behavior

For each button, `dispatcher.invoke(button.action, button.args)` is called on
click. `args` is whatever object you put in YAML — passed through verbatim.

### Variants

The 6 shadcn variants map directly to the shadcn `Button` component. Use
`destructive` for delete/remove actions, `outline` for secondary actions,
`ghost` for low-emphasis actions inside dense lists.

---

## `file-tree`

Recursive folder/file tree with expand/collapse, optional click-to-select on
files, and per-row hover-revealed actions.

### YAML

```yaml
- name: "Files"
  type: "file-tree"
  position: { horizontal: "left", vertical: "middle" }
  size: { width: 6, height: 400 }

  # Pick ONE source of nodes. Live data wins:
  data_source:                 # optional; returns FileTreeNode[]
    action: "list_user_files"
    args: { root: "/home" }
    subscribe: false
  nodes:                       # optional; static fallback
    - id: "1"
      name: "report.pdf"
      type: "file"
      size: 245000

  on_select: "open_file"       # optional; dispatched with { file: FileTreeNode } when a file is clicked

  file_actions:                # optional; hover-revealed buttons on each file row
    - name: "Open"
      action: "open_file"
    - name: "Rename"
      action: "rename_file"
    - name: "Delete"
      action: "delete_file"
      icon: "/assets/trash.svg"   # optional

  empty_text: "No files yet"   # optional
```

### `FileTreeNode` shape

```ts
type FileTreeNode = {
  id: string;
  name: string;
  type: "file" | "folder";
  size?: number;                 // bytes; only meaningful for files
  children?: FileTreeNode[];     // only meaningful for folders
};
```

The shape is recursive and validated with `z.lazy`. A folder may have a
`children` array; an empty folder is allowed (renders as an empty branch when
expanded).

### Resolution order

`useAgentInbox<FileTreeNode[]>().lastPayload` *(if a `tool-call` arrived)*
**→** `useWidgetData<FileTreeNode[]>(props.data_source).data` **→**
`props.nodes` **→** `[]`.

### Click behavior

- **Folder**: click the row to toggle expansion. The chevron rotates.
- **File**: if `on_select` is set, click invokes
  `dispatcher.invoke(on_select, { file })`.
- **Per-row actions**: `file_actions` buttons appear on hover (right side).
  Each invokes `dispatcher.invoke(action, { file })`. Clicking a per-row
  action does **not** trigger `on_select` — propagation is stopped.

### Sizes

The widget formats byte sizes (`245 B`, `12.4 KB`, `2.1 MB`, `1.34 GB`) when
`size` is present on a file node.

---

## `ai-chat-input`

User input box with a Send button. Submits go to the `AgentBridge`. Also
records the user's message in the conversation log read by `ai-history`.

### YAML

```yaml
- name: "chat-input"
  type: "ai-chat-input"
  position: { horizontal: "left", vertical: "low" }
  size: { width: 12, height: "auto" }
  placeholder: "Ask anything…"   # optional
  submit_label: "Send"           # optional
  rows: 2                        # optional; textarea rows, 1..20
```

### Submit flow

On Enter (or Send click) with non-empty trimmed text:

1. Pushes the text into the conversation log via `pushUserMessage()`.
2. If an `AgentBridge` is connected, calls `agent.onUserSubmit(text)`.
3. Otherwise, if `dispatcher.has?.("user-submit")` is true, falls back to
   `dispatcher.invoke("user-submit", { text })`.
4. Otherwise, the input is rendered inert with a dev-mode console warning.

Pressing **Shift+Enter** inserts a newline; **Enter alone** submits.

---

## `ai-response`

Streaming agent output panel. Reads from the `AgentBridge` event stream.

### YAML

```yaml
- name: "agent-output"
  type: "ai-response"
  position: { horizontal: "right", vertical: "middle" }
  size: { width: 6, height: 300 }
  empty_text: "Ask the agent something below."   # optional
```

### Event handling

| Event kind | Effect on `ai-response` |
|------------|------------------------|
| `token`    | Appends to the in-progress assistant bubble (coalesced by `messageId`). |
| `message`  | Finalizes the bubble (or appends a new one). |
| `status`   | Shows "…thinking" / "…responding" indicator. |
| `error`    | Appends a system-style error bubble. |
| `tool-call`| Ignored — those route to the targeted widget by `name`. |

### Empty state

If no `AgentBridge` is connected, or there are no messages yet, the widget
renders `empty_text` (or "No agent bridge connected." when truly inert).

---

## `ai-history`

Full conversation transcript: user messages, assistant messages, system
messages. A different view of the same data backing `ai-response`, plus the
user side which `ai-response` doesn't show.

### YAML

```yaml
- name: "history"
  type: "ai-history"
  position: { horizontal: "right", vertical: "middle" }
  size: { width: 6, height: 400 }
  empty_text: "No conversation yet."   # optional
  show_system: true                    # optional; default true
```

### What it shows

- **User** messages: right-aligned, primary color bubbles.
- **Assistant** messages: left-aligned, accent-color bubbles.
- **System** messages: centered, muted italic. Hidden if `show_system: false`.

Each row also shows a small `HH:MM · role` line beneath. Auto-scrolls to
bottom on new messages.

### Data source

Internal — populated by the provider, not by `data_source`:

- `ai-chat-input` calls `pushUserMessage(text)` on submit → user message lands
  here immediately.
- The provider's `subscribeAgentOutput` handler appends finalized `message`
  events from the `AgentBridge` (assistant + system).
- Errors land as system-role rows.

Token-only streams (no closing `message`) do **not** appear in history. Emit
a final `message` event to mark a turn complete.

### Reading the log from custom code

```ts
import { useConversation } from "agent-ui";

function MyWidget() {
  const { messages } = useConversation();
  return <pre>{JSON.stringify(messages, null, 2)}</pre>;
}
```

`useConversation` is also exported as a hook — use it from your own widgets
or host components if you want a different rendering of the same log.

---

## Tool-call routing (any widget)

The `AgentBridge` can push a typed payload directly to any widget by name:

```ts
emit({ kind: "tool-call", widget: "Files", payload: [/* FileTreeNode[] */] });
```

That payload becomes available to the widget named `"Files"` via:

```tsx
const { lastPayload, history } = useAgentInbox<FileTreeNode[]>();
```

`tool-call.widget` is **required** — events without it (or with a name not
matching any widget in the plan) are dropped with a diagnostic.

The two widgets that already wire this up are:

- `file-tree` — `lastPayload` (if any) wins over `data_source` and static
  `nodes`.
- Custom widgets you build — see [extending.md](./extending.md).

---

## Combining widgets — recipe

A typical "agent dashboard" assembles all 7 widgets:

```yaml
page:
  layout_type: "grid"
  main_color: "#2E86DE"

widgets:
  - name: "header"
    type: "page-header"
    position: { horizontal: "left", vertical: "high" }
    size: { width: 8, height: "auto" }
    title: "Operations Console"
    subtitle: "Real-time agent dashboard"

  - name: "actions"
    type: "button-group"
    position: { horizontal: "right", vertical: "high" }
    size: { width: 4, height: "auto" }
    buttons:
      - { label: "Refresh", action: "refresh", variant: "outline" }
      - { label: "New",     action: "create",  variant: "default" }

  - name: "Files"
    type: "file-tree"
    position: { horizontal: "left", vertical: "middle" }
    size: { width: 6, height: 400 }
    data_source: { action: "list_user_files" }
    on_select: "open_file"
    file_actions:
      - { name: "Open",   action: "open_file" }
      - { name: "Delete", action: "delete_file" }

  - name: "history"
    type: "ai-history"
    position: { horizontal: "right", vertical: "middle" }
    size: { width: 6, height: 400 }
    empty_text: "No conversation yet."

  - name: "agent-output"
    type: "ai-response"
    position: { horizontal: "left", vertical: "low" }
    size: { width: 12, height: "auto" }

  - name: "chat-input"
    type: "ai-chat-input"
    position: { horizontal: "left", vertical: "low" }
    size: { width: 12, height: "auto" }
    placeholder: "Ask the agent…"

  - name: "footer"
    type: "page-footer"
    position: { horizontal: "left", vertical: "low" }
    size: { width: 12, height: "auto" }
    text: "agent-ui · powered by shadcn"
```

The grid packer places `vertical: "high"` items first, then `middle`, then
`low`, packing left-to-right within each row. `width` numbers add to 12 per
row (header 8 + actions 4, files 6 + history 6, etc.).
