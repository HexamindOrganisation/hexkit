# Layout showcase

The same five widgets rendered under both `layout_type`s, switchable
from a top bar.

## What it shows

Same widget set in every config:

- `page-header` — title + subtitle naming the active layout
- `markdown` — short readme explaining the two layouts
- `form` — a "Run task" form with text / select / number / checkbox fields
- `button-group` — Refresh / Settings actions
- `page-footer` — footer text

The only differences between configs are the layout-specific bits:

| File          | `layout_type` | What changes |
|---------------|---------------|--------------|
| [`grid.yaml`](./grid.yaml)       | `grid`    | `position` + `size.width` place the readme and form side-by-side (6+6). |
| [`flex.yaml`](./flex.yaml)       | `flex`    | No `position`; widgets stack in config order, `width: 12` = 100%. |

## How to run

```bash
npm run example:layouts
```

Opens at <http://localhost:5175/>.

## What's wired up

- A **stub `ActionDispatcher`** that just `console.log`s every action it
  receives. Submit the form or click a button and watch the console — no
  backend involved.
- **No `AgentBridge`**. The chat widgets aren't included here; this
  example is about layout, not conversation.

## Notes on the switcher

The top bar isn't part of the library — it's a tiny React `<nav>` in
[`App.tsx`](./App.tsx) that swaps the `config` prop on `<AgentUI>` and
forces a remount with `key={layout}` so each layout starts fresh.
