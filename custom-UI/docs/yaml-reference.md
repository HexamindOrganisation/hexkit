# YAML reference

The shape of a config. For per-widget fields, see
[widgets.md](./widgets.md). For autocomplete in VS Code, emit a JSON Schema
once and link it at the top of your YAML:

```bash
npx agent-ui emit-schema > agent-ui.schema.json
```

```yaml
# yaml-language-server: $schema=./agent-ui.schema.json
```

## Top-level shape

A config has exactly two top-level keys:

```yaml
page:       # page-level settings (required)
  ...
widgets:    # array of widgets (optional, defaults to [])
  - ...
```

There is no header, footer, or chat container shell — anything the user sees
is a widget. Place a `page-header`, `ai-chat-input`, etc. as widgets.

## `page`

```yaml
page:
  layout_type: "grid"            # required; one of: grid | flex
  theme:                         # optional; pick a curated palette
    mode: "light"                #   "light" | "dark" | "system"
    accent: "#4F46E5"            #   any hex; flows to --primary, --ring, focus, hovers
    overrides:                   #   optional; raw CSS-var overrides (escape hatch)
      "--muted": "210 40% 90%"
      "--border": "214 32% 88%"
```

- **`layout_type`** determines how the `widgets` array is arranged — see
  [Layouts](#layouts).
- **`theme.mode`** picks the curated shadcn palette for that mode. `system`
  tracks `prefers-color-scheme` at runtime and switches automatically.
- **`theme.accent`** is one hex color. The resolver bridges it to
  `--primary` (used by buttons, user-message bubbles, focus rings, hover
  tints, etc.) plus a derived `--primary-foreground` for contrast. All
  other shadcn variables (`--background`, `--foreground`, `--card`,
  `--muted`, `--border`, `--input`, `--secondary`, `--destructive`, …)
  stay at the values tuned for the chosen mode — they're designed to work
  together; let them.
- **`theme.overrides`** is an escape hatch. Each entry is written verbatim
  as an inline CSS custom property on the AgentUI root. Use HSL triplets
  like `"210 40% 90%"` for shadcn variables (they're consumed via
  `hsl(var(--name))`). Reach for this only when a curated default truly
  doesn't fit.

## Common widget fields

```yaml
- name: "agent-output"           # required; unique within the config
  type: "ai-response"            # required; widget discriminator (see widgets.md)
  position:                      # optional; layout-specific hints
    horizontal: "left"           #   left | right | center
    vertical: "high"             #   high | middle | low
  size:                          # required
    width: 6                     #   1..12 (grid columns; ignored by flex)
    height: 400                  #   pixels, or "auto"
  # ...type-specific fields, see widgets.md
```

- **`name`** is how the `AgentBridge` addresses the widget in `tool-call`
  events and how `useAgentInbox()` scopes to a widget. Must be unique within
  the config. No reserved names — you can name a widget anything.
- **`position`** is meaningful for the `grid` layout. The packer
  sorts widgets by `vertical` and biases column choice by `horizontal`.
- **`size.width`** is a grid column count (1–12), **not pixels**. For `flex`
  it becomes a percentage of the container.
- **`size.height`** is pixels or the literal string `"auto"`.

### Footer-slot widgets bypass the layout

Some widget types are registered with `slot: "footer"` (currently
[`page-footer`](./widgets.md#page-footer)). Those widgets are pulled out of
the `widgets:` array before the layout is computed and rendered in a
dedicated footer slot, pinned to the bottom of the page. For these widgets
`position` is ignored and `size.width` always spans the full page. Custom
widgets can opt into the same behavior — see
[extending.md — slot](./extending.md#footer-slot-widgets).

## Layouts

> **See it side-by-side:** [`examples/layouts`](../examples/layouts) renders
> the **same five widgets** under both layouts with a top-bar switcher —
> the fastest way to feel how `layout_type` reshapes a page. Run it with
> `npm run example:layouts`.

### `layout_type: grid`

Twelve-column CSS grid, packed top-down/left-to-right with `position` biases.
Overflow (e.g. `width: 14`) emits a `layout.grid-overflow` diagnostic.

```yaml
page: { layout_type: "grid" }
widgets:
  - name: "left"
    type: "page-header"
    position: { horizontal: "left", vertical: "high" }
    size: { width: 6, height: "auto" }
    title: "Left panel"
  - name: "right"
    type: "button-group"
    position: { horizontal: "right", vertical: "high" }
    size: { width: 6, height: "auto" }
    buttons:
      - { label: "Go", action: "go" }
```

Vertical bias order: `high` → `middle` → `low`. Within a row, horizontal bias
(`left` / `center` / `right`) controls preferred column starts.

### `layout_type: flex`

Stacks widgets in config order. Ignores `position`. `size.width` becomes a
percentage of the container — `width: 6` → 50%, `width: 12` → 100%. Widgets
wrap if they don't fit.

## `data_source` — shared sub-schema

Any widget field named `data_source` has the same shape:

```yaml
data_source:
  action: "some-action-name"     # required
  args: { foo: 42 }              # optional; passed as the second arg to invoke()
  subscribe: true                # optional; uses dispatcher.subscribe if available
```

`subscribe: true` with a dispatcher that implements `subscribe` gives you
live updates. Otherwise it's a one-shot `invoke` when the widget mounts.

## Diagnostics codes

| Code | Meaning |
|---|---|
| `yaml.parse` | The YAML itself is malformed |
| `ajv.*` | A field is the wrong shape / type / missing (e.g. `ajv.required`, `ajv.enum`, `ajv.maximum`) |
| `resolve.missing-name` / `resolve.missing-type` | Widget is missing its discriminator fields |
| `resolve.duplicate-name` | Two widgets share the same `name` |
| `resolve.unknown-type` | The widget `type` isn't registered (renders a placeholder) |
| `resolve.unknown-action` | An `action` name isn't in `dispatcher.has()` (warning only) |
| `layout.grid-overflow` | `size.width` > 12 |
| `layout.grid-collision` | Packer couldn't place a widget after 512 rows |
| `agent.tool-call-no-widget` | `AgentBridge` sent a `tool-call` without a `widget` target |
| `agent.tool-call-unknown-widget` | `tool-call` targets a widget name that isn't in the plan |
| `agent.error` | `AgentBridge` emitted an `error` event |

Diagnostics include YAML source `line` and `col` when available, so clicking
through to the right spot in your config is usually trivial.
