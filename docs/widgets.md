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

| `type`           | Purpose                              | Chromeless | Slot   |
|------------------|--------------------------------------|------------|--------|
| `page-header`    | Title + optional subtitle/icon       | yes        | main   |
| `page-footer`    | Single-line footer                   | yes        | footer |
| `button-group`   | Row/column of action buttons         | no         | main   |
| `file-tree`      | Recursive folder/file tree           | no         | main   |
| `ai-chat-input`  | Textarea + send → AgentBridge        | yes        | main   |
| `ai-response`    | Live chat transcript (user + agent)  | yes        | main   |
| `ai-history`     | List of past conversations           | yes        | main   |
| `spacer`         | Empty cell — reserves layout space   | yes        | main   |

**Chromeless** widgets opt out of the default `<div class="au-widget-host">`
border/padding so they sit flush with the page edges.

**Slot** controls where a widget renders inside the AgentUI shell:

- `main` *(default)* — the widget participates in the layout
  (`grid` / `flex` / `sidebar` / `tabs`). Honors `position`, `size.width`,
  and `tab`.
- `footer` — the widget is rendered **outside** the layout, pinned to the
  bottom of the page no matter how short or tall the main content is.
  `position` is ignored. The footer slot spans the full page width.

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

A single-line footer pinned to the bottom of the page.

This widget renders in the **footer slot** — outside the layout. It always
sits at the bottom of the AgentUI shell, regardless of how short or tall
the main content is. If the main content is shorter than the viewport, the
footer pins to the viewport bottom; if it's taller, the footer sits at the
end of the document.

### YAML

```yaml
- name: "footer"
  type: "page-footer"
  size: { width: 12, height: "auto" }
  text: "© 2026 ACME · v1.2.0"   # optional
```

`position` is **not** required and is ignored — the footer is always last.
You can keep it in the YAML if you want, but it has no effect.

`size.width` is also effectively ignored: the footer slot spans the full
page width. `size.height` still applies if you set a fixed value, otherwise
the footer sizes to its content.

### Renders

A `<footer>` centered text band, muted foreground, top border. If `text` is
omitted, an empty footer band still renders (useful as a spacer).

### Multiple footers

If you place multiple `page-footer` widgets (or any custom widgets
registered with `slot: "footer"` — see [extending.md](./extending.md)),
they stack vertically in the footer slot in YAML order. The whole stack is
what gets pinned to the bottom.

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

Live chat transcript. Renders the conversation log (user + assistant +
system) **and** any in-flight assistant response that's still streaming
tokens.

### YAML

```yaml
- name: "agent-output"
  type: "ai-response"
  position: { horizontal: "right", vertical: "middle" }
  size: { width: 6, height: 300 }
  empty_text: "Ask the agent something below."   # optional
```

### What it shows

- **User** messages — right-aligned, primary color bubbles. Pushed into the
  log by `ai-chat-input` on submit.
- **Assistant** messages — left-aligned, accent-color bubbles. Pushed into
  the log by the provider when a `message` event arrives on the
  `AgentBridge`, **or** loaded into the log by `ai-history`.
- **System** messages — centered, muted italic. Pushed into the log on
  `error` events (and any system-role `message` events you emit).
- **Streaming partial** — a translucent assistant bubble that grows as
  `token` events stream in. When a final `message` with the same
  `messageId` arrives, the partial is dropped and the finalized bubble takes
  its place from the log.

The widget auto-scrolls to the bottom on every new message or token.

### Event handling

| Event kind | Effect on `ai-response` |
|------------|-------------------------|
| `token`    | Appended to (or starts) a translucent assistant bubble at the bottom, coalesced by `messageId`. |
| `message`  | Drops the matching partial; the provider has already added the finalized message to the log. |
| `status`   | Shows "…thinking" / "…responding" indicator. |
| `error`    | Provider appends a system-role row to the log; the widget renders it. |
| `tool-call`| Ignored — those route to the targeted widget by `name`. |

### Empty state

If the conversation log is empty, no partial is in flight, and status is
`idle`, the widget renders `empty_text` (or "No agent bridge connected."
when no bridge is wired).

---

## `ai-history`

Vertical, clickable list of **past conversations** (chats), pulled from a
host-defined data source. Selecting a conversation calls `on_select` to
fetch its messages and loads them into the conversation log read by
`ai-response`. Subsequent user submits and assistant replies append to the
loaded conversation.

### YAML

```yaml
- name: "history"
  type: "ai-history"
  position: { horizontal: "left", vertical: "middle" }
  size: { width: 3, height: 400 }
  data_source:                       # optional; returns ConversationSummary[]
    action: "list_conversations"
    args: { user_id: "u123" }        # optional
    subscribe: true                  # optional
  conversations:                     # optional; static fallback when no data_source
    - { id: "c1", title: "Welcome chat" }
  on_select: "load_conversation"     # required; invoked with { id }
  empty_text: "No past conversations"   # optional
```

### `ConversationSummary` shape

Each item the data source returns:

```ts
type ConversationSummary = {
  id: string;          // required, unique
  title: string;       // required, the clickable label
  preview?: string;    // optional, sub-text under the title
  timestamp?: number;  // optional, formatted as "Mon DD, HH:MM"
};
```

### `on_select` action

When a conversation is clicked, the widget invokes
`dispatcher.invoke(on_select, { id })`. The result must be either:

- An array: `ConversationMessage[]`, **or**
- An object with a `messages` property: `{ messages: ConversationMessage[] }`.

The `ConversationMessage` shape:

```ts
type ConversationMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
};
```

The returned messages are passed to the provider via `loadConversation(id,
messages)`, which:

1. Replaces the in-memory conversation log with the loaded messages.
2. Sets `selectedConversationId` so `ai-history` can highlight the active
   row.

After load, `ai-response` re-renders with the loaded transcript. Continuing
the chat appends new user/assistant turns to that log.

### Highlighting the active conversation

The button for the conversation whose id matches `selectedConversationId`
gets `aria-selected="true"` and an `accent` background. Clicking another
conversation switches the active one — the previous one's in-memory
appendings are **lost** unless the host has persisted them (typically by
intercepting `pushUserMessage` and assistant `message` events to write to
storage).

### Reading the log from custom code

```ts
import { useConversation } from "agent-ui";

function MyView() {
  const { messages } = useConversation();
  return <pre>{JSON.stringify(messages, null, 2)}</pre>;
}
```

To trigger conversation loading from your own widget:

```ts
import { useAgentUIContext, type ConversationMessage } from "agent-ui";

function MyConversationPicker() {
  const { loadConversation } = useAgentUIContext();
  // ...
  loadConversation("conversation-id", messages);
}
```

---

## `spacer`

An empty widget that renders nothing. Use it to reserve a cell in the
layout — useful for pushing other widgets around without resorting to
`position` tricks.

### YAML

```yaml
- name: "left-pad"
  type: "spacer"
  position: { horizontal: "left", vertical: "high" }
  size: { width: 4, height: "auto" }
```

The widget itself is invisible; what matters is that it occupies a cell
with the `width` and `height` you give it. Common patterns:

- **Push a widget right.** Place a `spacer` with `horizontal: "left"` at
  the same `vertical` row as the widget you want to nudge — the grid
  packer fills the spacer's cells first, so the next widget lands further
  right.
- **Reserve vertical space.** A `spacer` with a fixed pixel height creates
  a gap row between busy sections.
- **Empty cell in `tabs` layout.** Put a `spacer` in a `tab` panel that's
  intentionally blank.

It honors all the standard widget-base fields (`name`, `position`, `size`,
`tab`) and nothing else.

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
    size: { width: 3, height: 400 }
    data_source: { action: "list_conversations" }
    on_select: "load_conversation"

  - name: "agent-output"
    type: "ai-response"
    position: { horizontal: "right", vertical: "middle" }
    size: { width: 3, height: 400 }

  - name: "chat-input"
    type: "ai-chat-input"
    position: { horizontal: "left", vertical: "low" }
    size: { width: 12, height: "auto" }
    placeholder: "Ask the agent…"

  - name: "footer"
    type: "page-footer"
    size: { width: 12, height: "auto" }
    text: "agent-ui · powered by shadcn"   # rendered in the footer slot, always at the page bottom
```

The grid packer places `vertical: "high"` items first, then `middle`, then
`low`, packing left-to-right within each row. `width` numbers add to 12 per
row (header 8 + actions 4, files 6 + history 6, etc.).
