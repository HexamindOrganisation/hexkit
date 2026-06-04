# Configuring widgets

Every visible thing in an agent-ui page is a widget. There is no special header,
footer, or chat container shell — they are all widgets you place via the
`widgets:` array in YAML.

This page documents every native widget: its `type`, its YAML schema, what it
renders, and what runtime hooks it consumes.

For the *envelope* every widget shares (`name`, `position`, `size`),
see [yaml-reference.md](./yaml-reference.md#common-widget-fields). For
custom widgets, see [extending.md](./extending.md).

## Widget catalog

| `type`           | Purpose                              | Chromeless | Slot   |
|------------------|--------------------------------------|------------|--------|
| `page-header`    | Title + optional subtitle/icon       | yes        | main   |
| `page-footer`    | Single-line footer                   | yes        | footer |
| `button-group`   | Row/column of action buttons         | no         | main   |
| `ai-chat-input`  | Textarea + send → AgentBridge        | yes        | main   |
| `ai-response`    | Live chat transcript (user + agent)  | yes        | main   |
| `spacer`         | Empty cell — reserves layout space   | yes        | main   |
| `markdown`       | Renders markdown text safely         | no         | main   |
| `form`           | Schema-driven form → dispatcher      | no         | main   |
| `metrics`        | Strip of stat cards from a data source | no       | main   |
| `table`          | Scrollable CSV table (head/tail rows)  | no         | main   |
| `tool-calls`     | Live log of agent tool invocations     | no         | main   |

**Chromeless** widgets opt out of the default `<div class="au-widget-host">`
border/padding so they sit flush with the page edges.

**Slot** controls where a widget renders inside the AgentUI shell:

- `main` *(default)* — the widget participates in the layout
  (`grid` / `flex`). Honors `position` and `size.width`.
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

## `ai-chat-input`

User input box with two icon-only buttons stacked next to the textarea:
a **send** button (right arrow) on top and a **cancel** button (filled
square, destructive variant) below. Submits go to the `AgentBridge`; the
cancel button invokes the dispatcher's `cancel-run` action.

### YAML

```yaml
- name: "chat-input"
  type: "ai-chat-input"
  position: { horizontal: "left", vertical: "low" }
  size: { width: 12, height: "auto" }
  placeholder: "Ask anything…"   # optional
  submit_label: "Send"           # optional; screen-reader label for the send button
  rows: 2                        # optional; textarea rows, 1..20
```

### Submit flow

On Enter (or click on the send arrow) with non-empty trimmed text:

1. Pushes the text into the conversation log via `pushUserMessage()`.
2. If an `AgentBridge` is connected, calls `agent.onUserSubmit(text)`.
3. Otherwise, if `dispatcher.has?.("user-submit")` is true, falls back to
   `dispatcher.invoke("user-submit", { text })`.
4. Otherwise, the input is rendered inert with a dev-mode console warning.

Pressing **Shift+Enter** inserts a newline; **Enter alone** submits.

### Cancel button

- **Disabled** when no run is in flight; **enabled** while submitting.
- On click, calls `dispatcher.invoke("cancel-run")`. The host wires this
  action to whatever stops the agent (commonly `bridge.cancel()`).
- Dispatcher errors are swallowed silently — the UI has nothing visual
  to roll back, and a failed cancel call is a deployment issue, not a
  user-visible one.

### Accessibility

- The icons are decorative (`aria-hidden`); each button's accessible
  name comes from `aria-label`. Defaults: "Send" and "Cancel run".
- `submit_label` overrides the send button's label; the cancel button's
  label is fixed in v0 (`"Cancel run"`).

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
  thinking_indicator: "dots"                     # optional: "dots" | "text" | "none" (default "dots")
  thinking_text: "…thinking"                     # optional: text shown when indicator is "text", and aria-label for "dots"
  responding_text: "…responding"                 # optional: shown briefly between status=responding and the first token
```

### What it shows

- **User** messages — right-aligned, primary color bubbles. Pushed into the
  log by `ai-chat-input` on submit.
- **Assistant** messages — left-aligned, accent-color bubbles. Pushed into
  the log by the provider when a `message` event arrives on the
  `AgentBridge`.
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
| `status`   | `thinking` shows the loading indicator (animated dots by default) when no tokens have arrived yet; `responding` shows `responding_text` until the first token; `idle` clears both. |
| `error`    | Provider appends a system-role row to the log; the widget renders it. |
| `tool-call`| Ignored — those route to the targeted widget by `name`. |

### Empty state

If the conversation log is empty, no partial is in flight, and status is
`idle`, the widget renders `empty_text` (or "No agent bridge connected."
when no bridge is wired).

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

It honors all the standard widget-base fields (`name`, `position`, `size`)
and nothing else.

---

## `markdown`

Renders a string of markdown as styled, **safe** rich text. Useful for help
panels, release notes, model-system-card displays, or piping a long-form
LLM answer through a dispatcher action and showing it formatted.

### YAML

```yaml
# Inline content:
- name: "help"
  type: "markdown"
  size: { width: 6, height: "auto" }
  content: |
    ## Quick start
    Type a message below and hit **send**.
    See [the docs](https://example.com/docs).

# Or bound to a dispatcher action returning a string:
- name: "release-notes"
  type: "markdown"
  data_source: { action: "fetch_release_notes", subscribe: false }
  empty_text: "No notes yet."
```

### Fields

| Field         | Type                | Notes |
|---------------|---------------------|-------|
| `content`     | string              | Inline markdown source. |
| `data_source` | `DataSource`        | Fetched via the dispatcher; resolved value must be a string. |
| `empty_text`  | string              | Shown while loading or when the source is empty. |

`content` and `data_source` are mutually exclusive — provide one.

### Supported markdown

Headings (`#`–`######`), paragraphs, **bold**, *italic*, `inline code`,
fenced code blocks (```` ``` ````), bullet/ordered lists, blockquotes,
horizontal rules, and links.

### Security

The renderer is **safe by construction**:

- Output is React nodes only — no `dangerouslySetInnerHTML`. React's
  text-escaping is the security boundary, so any text in the source becomes
  literal text in the DOM.
- Raw HTML in the markdown source is **not** parsed; it renders as plain
  text (e.g. `<script>` shows up as the literal string).
- Code blocks are display-only — they never execute. The optional
  `lang` after the opening fence is exposed as a `data-language` attribute
  for syntax-highlighting plugins, but no JS runs.
- Link URLs are scheme-validated. Only `http:`, `https:`, `mailto:`, and
  relative URLs (`/`, `#`, `?`, `./`, `../`) are emitted as `<a href>`. Any
  other scheme — `javascript:`, `data:`, `vbscript:`, `file:`, etc. — is
  rejected and the link label is rendered as plain text.
- All emitted links use `target="_blank"` with `rel="noopener noreferrer nofollow"`.
- No images, no inline HTML attributes, no event handlers — there is no
  surface to attach JavaScript to.

If you need richer features (tables, images, syntax highlighting, GFM),
register a custom widget that wraps a vetted library like `react-markdown`
with `rehype-sanitize`.

---

## `form`

Schema-driven form. Each field renders the right control; on submit the
collected values are dispatched as a single action through the
`ActionDispatcher`. Useful for parametrizing an agent run, configuring a
tool before invoking it, or collecting structured input that's awkward to
extract from chat.

### YAML

```yaml
- name: "new-job"
  type: "form"
  size: { width: 6, height: "auto" }
  submit_action: "create_job"
  submit_label: "Run job"
  reset_label: "Reset"           # optional: shows a reset button
  columns: 2                     # optional: 1–4, default 1
  reset_on_success: true         # optional
  success_message: "Job queued." # optional
  fields:
    - id: "name"
      label: "Job name"
      type: "text"
      required: true
      max_length: 60
      placeholder: "weekly-rollup"
    - id: "model"
      label: "Model"
      type: "select"
      default: "claude-opus-4-7"
      options:
        - { label: "Opus 4.7", value: "claude-opus-4-7" }
        - { label: "Sonnet 4.6", value: "claude-sonnet-4-6" }
        - { label: "Haiku 4.5", value: "claude-haiku-4-5-20251001" }
    - id: "max_steps"
      label: "Max steps"
      type: "number"
      default: 10
      min: 1
      max: 100
    - id: "instructions"
      label: "Instructions"
      type: "textarea"
      rows: 4
    - id: "dry_run"
      label: "Dry run only"
      type: "checkbox"
      default: false
```

### Submit payload

The dispatcher receives `{ ...submit_args, ...values }` for `submit_action`,
where `values` is keyed by each field's `id`. With the example above:

```ts
dispatcher.invoke("create_job", {
  name: "weekly-rollup",
  model: "claude-opus-4-7",
  max_steps: 10,
  instructions: "…",
  dry_run: false,
});
```

If the action throws, the error message is shown beside the submit button.
On success, `success_message` is shown and the form resets if
`reset_on_success: true`.

### Field types

| `type`              | Control            | Value type | Extra fields |
|---------------------|--------------------|------------|--------------|
| `text`              | single-line input  | string     | `placeholder`, `default`, `min_length`, `max_length`, `pattern` |
| `email` / `url` / `password` / `search` / `tel` | input | string | same as `text` (with built-in validation for `email` / `url`) |
| `textarea`          | multi-line input   | string     | `placeholder`, `default`, `rows`, `min_length`, `max_length` |
| `number`            | number input       | number     | `placeholder`, `default`, `min`, `max`, `step` |
| `checkbox`          | checkbox           | boolean    | `default` |
| `select`            | native `<select>`  | string     | `options` (required), `default`, `placeholder` |
| `radio`             | radio group        | string     | `options` (required), `default` |
| `date` / `time` / `datetime-local` | date input | string | `default`, `min`, `max` |

All field types share `id`, `label`, `required`, `help`, `disabled`.

### Prefilling

Bind `data_source` to a dispatcher action that returns a record keyed by
field `id`s; the form seeds those values on mount and re-seeds whenever
the source changes:

```yaml
- name: "edit-job"
  type: "form"
  data_source: { action: "load_job", args: { id: "abc" } }
  submit_action: "save_job"
  submit_args: { id: "abc" }
  fields: [ … ]
```

### Validation

Validation runs client-side before dispatch:

- `required` — non-empty string, true checkbox, or numeric value
- `min_length` / `max_length` — string fields
- `min` / `max` — numbers and date inputs
- `pattern` — RegExp source applied to text-like fields
- `email` / `url` types apply built-in format checks

Server-side validation should be enforced in the dispatcher action — throw
an `Error` with a useful message and the form will surface it.

---

## `metrics`

Horizontal strip of stat cards. Each cell shows a label, a formatted value,
and (optionally) a delta indicator and a hint line. Values come from a
`data_source` action; if the action also supports `subscribe: true`, the
strip updates live.

### YAML

```yaml
- name: "stats"
  type: "metrics"
  size: { width: 12, height: "auto" }
  data_source:
    action: "get_session_metrics"
    subscribe: true                 # optional; live updates if dispatcher.subscribe
  columns: 4                        # optional: 1–6 (otherwise wraps via flex)
  metrics:
    - id: "tokens"
      label: "Tokens"
      format: "number"
    - id: "cost"
      label: "Cost"
      format: "currency"
      precision: 4
    - id: "latency"
      label: "p95 latency"
      format: "duration"
    - id: "success"
      label: "Success rate"
      format: "percent"
      precision: 1
```

### Dispatcher payload

The action returns a record keyed by each metric's `id`. Each value can be
a primitive or an object with optional `delta` / `hint`:

```ts
type MetricsPayload = Record<string, number | string | {
  value: number | string;
  delta?: number;     // ▲ green for > 0, ▼ rose for < 0; 0 hides the badge
  hint?: string;      // muted second line on the card
}>;
```

Example return value matching the YAML above:

```ts
{
  tokens: { value: 18420, delta: 1240, hint: "this session" },
  cost: 0.0732,
  latency: { value: 312, hint: "rolling 5 min" },
  success: { value: 0.973, delta: 0.014 },
}
```

Cells without a corresponding key in the payload render as `—`.

### Format types

| `format`    | Input shape                         | Renders as                  |
|-------------|-------------------------------------|-----------------------------|
| `number`    | number                              | `1,234.56` (locale-aware)   |
| `percent`   | number                              | `0.42` → `42.0%` (or `42` → `42%` if already > 1) |
| `currency`  | number                              | `$1,234.56` (use `prefix` to override symbol) |
| `duration`  | number of milliseconds              | `850μs` / `42ms` / `3.20s` / `1m 12s` / `2h 5m` |
| `bytes`     | number of bytes                     | `1.5 MB` / `820 KB`         |
| `string`    | string                              | as-is, with prefix/suffix   |

`precision` controls decimal places for numeric formats. `prefix` and
`suffix` wrap the formatted value (e.g. `prefix: "≈ "`, `suffix: " req/s"`).

### Layout

- `columns: N` — fixed grid (1–6 columns on wide screens, gracefully
  collapsing on narrow viewports).
- omitted — flex wraps with `min-w: 120px` per cell.

### States

- No `data_source` → renders `empty_text` (or "No data_source configured.").
- `data_source` loading and no payload yet → renders `loading_text` (or
  "Loading metrics…").
- `data_source` errored → renders the error message in muted destructive text.

---

## `table`

Scrollable table that renders a CSV. The CSV can be inline or fetched from a
dispatcher action. A `mode` (`head` | `tail`) and `rows` parameter limit how
many data rows are displayed.

### YAML

```yaml
# Inline CSV:
- name: "preview"
  type: "table"
  size: { width: 12, height: 320 }
  content: |
    name,role,joined
    Ada,engineer,2024-03-01
    Linus,maintainer,2023-11-12
    Grace,architect,2022-06-30
  mode: "head"        # optional: "head" (default) | "tail"
  rows: 20            # optional: number of data rows to show, default 20
  has_header: true    # optional: treat first row as header, default true
  delimiter: ","      # optional: single-char delimiter; auto-detected by default

# Or bound to a dispatcher action returning a CSV string:
- name: "logs"
  type: "table"
  size: { width: 12, height: 400 }
  data_source:
    action: "load_logs_csv"
    args: { path: "/var/log/app.csv" }
    subscribe: false
  mode: "tail"
  rows: 50
  empty_text: "No log rows yet."
```

### Fields

| Field          | Type                          | Notes |
|----------------|-------------------------------|-------|
| `content`      | string                        | Inline CSV text. Ignored when `data_source` is set. |
| `data_source`  | `DataSource`                  | Returns CSV. See "Payload shapes". |
| `mode`         | `"head"` \| `"tail"`          | Take rows from the start or end. Defaults to `"head"`. |
| `rows`         | integer (1–10000)             | Number of data rows shown. Defaults to `20`. The header row, if any, is always shown and does not count toward this limit. |
| `delimiter`    | single character              | CSV delimiter. Defaults to auto-detect among `,`, `;`, `\t`, `\|`. |
| `has_header`   | boolean                       | Treat the first row as a sticky header. Defaults to `true`. |
| `empty_text`   | string                        | Shown when no source is configured or the payload is empty. |
| `loading_text` | string                        | Shown while `data_source` is loading and no payload has arrived. |

> **Note:** `rows` is named distinctly from the widget-base layout `size`,
> which controls the cell footprint. Use `size.height` to make the table
> visibly scrollable (the rows scroll inside the configured height; the
> header stays pinned).

### Payload shapes

The dispatcher action may return any of:

- A CSV string: `"a,b,c\n1,2,3\n4,5,6"`
- An object: `{ csv: "a,b,c\n…" }`
- A 2D array of rows: `[["a","b","c"],["1","2","3"]]` — already parsed.
  When supplied this way, `delimiter` is ignored.

### Parsing

The built-in CSV parser is RFC 4180–style: it supports quoted fields,
embedded delimiters, embedded newlines, and `""` as an escaped quote.
Carriage returns (`\r`) are stripped. Trailing empty lines are ignored.

### Layout

- The widget renders inside its layout cell. Use `size.height: <pixels>`
  to make it scroll. With `height: "auto"`, the table grows to fit all
  selected rows and only scrolls horizontally if needed.
- The header (when `has_header` is true) sticks to the top of the scroll
  container.
- A small footer line shows `Showing N of M rows (head|tail)`.

### States

- No `content` and no `data_source` → renders `empty_text` (or "No data.").
- `data_source` loading and no payload yet → renders `loading_text`
  (or "Loading table…").
- `data_source` errored → renders the error message in muted destructive text.

---

## `tool-calls`

Live log of tool invocations made by the agent. Each row corresponds to
one tool call; the row updates from "running" → "done" / "error" as the
agent emits events. Rows are click-to-expand and show arguments + output
JSON.

### YAML

```yaml
- name: "tool-calls"
  type: "tool-calls"
  position: { horizontal: "right", vertical: "middle" }
  size: { width: 4, height: 480 }
  title: "Tool calls"           # optional; header label
  empty_text: "No tools called yet."   # optional
  max_items: 50                 # optional; oldest rows dropped past this cap
  default_expanded: false       # optional; if true, rows start expanded
```

### Wire model

The widget consumes events routed via the `AgentBridge`'s `tool-call`
event. The bridge emits one payload per phase, keyed by a stable `id`:

```ts
type ToolCallPayload =
  | { phase: "start"; id: string; name: string; arguments?: object }
  | { phase: "end";   id: string; name?: string; output?: unknown; error?: string | null };
```

The widget folds the inbox history into one row per `id`. `start`
opens a row in the "running" state (amber pulsing dot). The matching
`end` finalizes the row to "done" (green) or "error" (red) and reveals
its output or error message.

### Bridge contract

The bridge sends events using the standard widget-name routing
described under [Tool-call routing](#tool-call-routing-any-widget):

```ts
emit({
  kind: "tool-call",
  widget: "tool-calls",          // must match the widget's `name`
  payload: { phase: "start", id: "abc", name: "search", arguments: { q: "x" } },
});
```

A widget named anything other than `"tool-calls"` is fine — the bridge
just needs to know the configured name. The convention `"tool-calls"`
is what the platform-runtime's [front-app](https://github.com/…) bridge
uses by default.

### Fields

| Field              | Type    | Notes |
|--------------------|---------|-------|
| `title`            | string  | Header label above the list. Optional. |
| `empty_text`       | string  | Shown before any tool call arrives. |
| `max_items`        | integer | Hard cap on displayed rows (oldest dropped). Default unlimited. |
| `default_expanded` | boolean | If true, every row starts with arguments + output visible. Default `false`. |

### Why a dedicated widget

Tool calls used to appear as `[tool] foo(args)` and `[result] foo -> ...`
system messages in `ai-response`. That mixed tool noise into the
human-readable transcript. Routing tool events to their own widget keeps
the chat focused on user/assistant text and lets the UI grow a richer
tool view (status indicators, JSON pretty-print, expand/collapse)
without bloating `ai-response`.

---

## Tool-call routing (any widget)

The `AgentBridge` can push a typed payload directly to any widget by name:

```ts
emit({ kind: "tool-call", widget: "tool-calls", payload: { phase: "start", id: "abc", name: "search" } });
```

That payload becomes available to the widget named `"tool-calls"` via:

```tsx
const { lastPayload, history } = useAgentInbox<ToolCallPayload>();
```

`tool-call.widget` is **required** — events without it (or with a name not
matching any widget in the plan) are dropped with a diagnostic.

The built-in widget that already wires this up is:

- `tool-calls` — folds the inbox `history` into one row per call `id`.

Custom widgets you build can do the same — see
[extending.md](./extending.md).

---

## Combining widgets — recipe

A typical "agent dashboard" assembles the chat-oriented widgets together:

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

  - name: "agent-output"
    type: "ai-response"
    position: { horizontal: "left", vertical: "middle" }
    size: { width: 8, height: 400 }

  - name: "tool-calls"
    type: "tool-calls"
    position: { horizontal: "right", vertical: "middle" }
    size: { width: 4, height: 400 }

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
row (header 8 + actions 4, agent-output 8 + tool-calls 4, etc.).
