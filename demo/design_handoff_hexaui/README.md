# Handoff: HexaUI — multi-agent platform UI

## Overview

HexaUI is a single chat platform that hosts **many agents** (operations,
research, code, finance, monitoring, integrations). Each agent's UI is
**configured by its developer in YAML** by composing pre-styled template
**widgets**, on top of one constant, minimalist chrome shell. The defining
idea: the platform ships a unified look, so developers *compose* layouts, they
don't *style* them — and the only color in the product is the **active agent's
signature hue**.

This bundle is the design reference for that product. Your job is to implement
it in the real codebase.

## About the design files

**The files in this bundle are design references created in HTML/React-via-Babel
— prototypes showing the intended look and behavior, not production code to
copy directly.** They run in a browser with no build step (Babel transpiles in
the page) and use plain CSS custom properties.

The target codebase is the **`agent-ui` library** (React + TypeScript +
shadcn/ui + Tailwind), documented in the repo you already have
(`README.md`, `docs/widgets.md`, and the widget `.tsx` reference files). Your
task is to **recreate these designs as the theme + configuration layer of that
library** — *not* to ship the HTML. Concretely that means:

1. Port the HexaUI tokens into the library's shadcn/Tailwind theme layer.
2. Build the chrome shell as a host wrapper around `<AgentUI>`.
3. Author each agent's MAIN region in YAML using the native widgets.
4. Restyle/confirm the two chat widgets to match the prototype.

If you are starting a brand-new app instead of the `agent-ui` library, keep the
same architecture (chromeless widget renderer + host shell + theme bridge) in
whatever framework fits.

## Fidelity

**High-fidelity.** Final colors, typography, spacing, motion, and interactions
are all specified below and embodied in the HTML. Recreate pixel-faithfully
using the codebase's components — but reproduce the *tokens and structure*, not
the literal HTML markup.

---

## The single most important mechanism: the theme bridge

The whole product recolors from **one variable**. shadcn tokens map straight
onto the HexaUI scale, so once the bridge is in place, every native widget
inherits the look automatically.

| shadcn / Tailwind token | HexaUI token |
|---|---|
| `background` | `--bg` |
| `card`, `popover` | `--surface` |
| `muted` | `--surface-2` / `--bg-2` |
| `border` | `--line` / `--line-2` |
| `foreground` | `--text` |
| `muted-foreground` | `--text-2` / `--text-3` |
| `primary`, `accent`, `ring` | **`--accent` (= the active agent's color = `page.main_color`)** |
| `destructive` | `--danger` |
| `radius` | `--r-md` |

**Implementation:** map these in the library's `shadcn.css` / `style.css` /
`tailwind-preset`, and set `--accent` (and shadcn `--primary`) from
`page.main_color` at the page root. Switching an agent = changing that one
value; do **not** override colors per widget.

`theme.css` in this bundle is the source of truth for every token, the chrome,
the chat, and all motion. `widgets.css` is the source of truth for widget
chrome restyled in those tokens (it is the reference for what the native
library widgets should look like once themed).

---

## Design tokens

### Typography
- **UI / body:** Hanken Grotesk — 15px body, 13.5px secondary, 600 for emphasis.
- **Display / greeting / long-form answers:** Source Serif 4 (alts: Libre Baskerville, Newsreader). Greeting 42–47px, weight 400, letter-spacing −0.01em.
- **Data / code / identifiers / labels:** IBM Plex Mono. Uppercase micro-labels 11–11.5px, letter-spacing 0.05em, color `--text-3`.

### Color — dark scale
| Token | Hex |
|---|---|
| `--bg` | `#1e1e1f` |
| `--bg-2` | `#181819` |
| `--surface` | `#282829` |
| `--surface-2` | `#323234` |
| `--surface-3` | `#3d3d40` |
| `--text` | `#ecedef` |
| `--text-2` | `#a3a6ac` |
| `--text-3` | `#6e7177` |
| `--line` | `rgba(240,242,245,0.10)` |
| `--line-2` | `rgba(240,242,245,0.055)` |

### Color — light scale
`--bg #ffffff` · `--bg-2 #f5f6f7` · `--surface #ffffff` · `--surface-2 #f0f1f3` ·
`--surface-3 #e7e9ec` · `--text #191c21` · `--text-2 #5c616a` · `--text-3 #969ba3` ·
`--line rgba(20,24,31,.11)` · `--line-2 rgba(20,24,31,.05)`.

### Semantic (widgets)
`--ok` sage `#7f9a6c` (light `#5d784a`) · `--danger` rose `#c4787f` (light `#b9555f`) ·
`--warn` amber `#c79a52`.

### Agent accent roster
| Agent | Role | Color |
|---|---|---|
| Atlas | Operations copilot | `#4f74c9` |
| Probe | Research & retrieval | `#3f9d94` |
| Forge | Code & build | `#56809e` |
| Sentry | Monitoring & safety | `#c79a52` |
| Ledger | Finance operations | `#c2788f` |
| Relay | Integrations & RPA | `#c07a55` |

### Radii, spacing, elevation
`--r-sm 7px` · `--r-md 11px` · `--r-lg 16px` · `--r-pill 999px`.
Density (comfortable default): `--pad 20`, `--gap 14`, `--row-h 38`. Compact:
`14 / 10 / 32`. One shadow token `--shadow: 0 1px 2px rgba(0,0,0,.35), 0 12px 34px rgba(0,0,0,.34)` — used **only** on the composer and floating menus; everything else is flat with hairline borders.

---

## Architecture — three layers

### 1. Chrome (constant; NOT agent-configured)
The `agent-ui` library is chromeless by design. Build the chrome as a **host
shell that wraps `<AgentUI>`**, which renders only the MAIN region.

- **Sidebar** (`--bg-2`, 260–270px): brand ("Hexa**UI**"), "New session", nav, then two sections:
  - **Conversation history** — **shared across ALL agents.** Every agent's conversations appear together regardless of which agent is active. Each row is prefixed with its agent's colored glyph (an 18px rounded square in the agent color with the agent's initial). Selecting a row switches to that agent, loads the chat, and swaps the MAIN layout. Active row uses `--surface-2` background.
  - **Workspace file tree** — labeled per agent (Repository / Statements / Documents / Connectors). Recursive, rotating chevron, mono byte sizes, hover-revealed row actions.
  - Footer: user avatar + name.
- **Top bar** (58px): the agent picker (avatar + name + chevron → searchable agent menu), session title in `--text-3`, history + overflow icons on the right.
- **Composer** and **transcript** — see "Chat" below. Constant across agents.

> Note: the standalone `page-header` widget was intentionally **removed** — agent identity lives in the top bar. Conversation history is **chrome, not a widget**.

### 2. MAIN widgets (agent-configured, in YAML)
The configurable region. Restyle the native library widgets via the theme
bridge; `widgets.css` shows the target appearance for each.

| `type` | Appearance notes |
|---|---|
| `metrics` | Stat cards on `--surface`/`--line`. Uppercase 10.5px label, 22–25px tabular-figure value, delta badge (`--ok` ▲ / `--danger` ▼), muted hint. |
| `table` | `--line` wrapper, sticky uppercase header on `--bg-2`, hairline rows, even-row tint `color-mix(--surface-2 45%)`, mono numerics, mono "Showing N of M" foot. |
| `markdown` | Serif `h2`, accent-underlined links, mono code chips on `--surface-2`, blockquote with `--line` left rule. |
| `button-group` | 6 variants: default = accent fill / `--bg` text; secondary = `--surface-2`; outline = `--line` border; ghost; destructive = rose tint; link = accent. Heights 28/34/40. |
| `form` | Inputs on `--bg-2` with `--line` border, focus border = `--accent-line`. Required `*` and focus ring in accent. Submit is the only filled (accent) control. |
| `tool-calls` | Rows on `--bg-2`. Status dot: amber pulsing (running) → `--accent` (done) → `--danger` (error). Click to expand mono JSON args/output. |
| `ai-response` / `ai-chat-input` | Constant chat — see below. |

### 3. Agent identity (the only color)
Chrome is monochrome. The active agent's hue tints the avatar, send button,
focus rings, links, hero rule, metric deltas, tool dots, and the streaming
caret — all via `--accent`.

---

## Chat — prototype design (constant)

- **User turn:** right-aligned bordered card (`.ucard`: `--surface`, `--line`, `--r-md`, ~78% max-width).
- **Assistant turn:** 30px agent-color avatar + name + a 20×2px accent tick + timestamp, then prose on the canvas (no bubble). May include a code block and copy / regenerate hover actions.
- **Thinking:** a liquid metaball loader (three blurred dots via the `#hx-goo` SVG filter) under a shimmering status line; avatar pulses in the agent color.
- **Streaming:** answer types in char-by-char trailing a blinking block caret in the agent color.
- **Composer:** one quiet field; attach icon left, voice + send right. **No agent selector in the input** (picker is in the top bar). Send is dimmed until there's text, then lights to the accent; border → `--accent-line` on focus. Enter submits, Shift+Enter newline.

---

## Layout examples — the six agents (real use cases)

Chrome + chat stay constant; the MAIN region differs per agent. `HexaUI Agent Layouts.html`
shows all six full-page; `prototype-widgets.jsx` shows how they're wired in the prototype.

| Agent | Use case | MAIN layout |
|---|---|---|
| Atlas | Incident response | metrics strip (top) · transcript · live tool-calls panel (right ~322px) |
| Forge | Coding workspace | repo file-tree in menu · PR/CI action bar (top) · transcript · tool-calls (~340px) |
| Ledger | Reconciliation | finance metrics (top) · invoice table (lead) · transcript side rail (~430px panel) |
| Probe | Research desk | history-led · transcript · cited Sources markdown panel (~320px) |
| Relay | Integration builder | configure-sync form panel (~380px) · transcript |
| Sentry | Monitoring | fleet metrics (top) · recent-audits tool-calls (~322px) |

**Prototype wiring contract:** `window.AgentWidgets[agentId] = { top?(ctx), side?(ctx), sideTitle, sideWidth }`, where `ctx = { pending }`. `top` renders above and `side` beside the centered chat; both inherit `--accent`. Tool-call panels show a live "running" row while `pending` is truthy. Translate this to: per-agent YAML config selected by the active agent.

---

## Interactions & behavior

- **Agent switch** (via top-bar picker OR selecting a shared-history conversation): set `--accent`/`main_color` to the new agent; swap the MAIN YAML layout; load the conversation. Motion (all transform-only, from `theme.css`): accent **bloom** behind the avatar (~0.6s), avatar **settle** (scale 0.82→1) and idle **breathe** ring, **thinking** stronger pulse.
- **Send:** push user message → `AgentBridge.onUserSubmit(text)` → stream `status`/`token`/`message` into `ai-response`; `tool-call` events route to the `tool-calls` widget by name.
- **History select:** load that conversation's messages into the log; highlight the active row.
- **New session:** clears the log, replays the greeting.
- **Streaming cadence in the prototype** is simulated (`app.jsx` `run()`); in the PoC it comes from the real bridge.

## State management

- `agentId` (active agent) → drives `--accent` + MAIN layout + composer placeholder + suggestion chips.
- **Shared conversation store** (cross-agent) → feeds `ai-history`; the library's per-session log is not enough, this needs host persistence.
- `messages`, `pending` (in-flight turn: `thinking` → `answering`), `activeConversationId`, plus UI state (sidebar collapsed, theme, density, hero face).
- Data sources per widget via `ActionDispatcher.invoke(action, args)`; live widgets via `subscribe`.

## Wiring contracts (from the library docs)
- **`ActionDispatcher`** — every widget `data_source` (metrics, table, file tree, history) resolves here.
- **`AgentBridge`** — `token` / `message` / `status` / `tool-call` / `error`; `tool-call.widget` must match the target widget's `name`.
- Hooks: `useWidgetData`, `useAgentInbox`, `useConversation`, `useAgentUIContext`.

## Assets
No raster assets. The Hexamind logo and all icons are inline SVG line icons
(`icons.jsx`) — recreate as a small icon set or map to your icon library
(Lucide is a close match). Avatars are letter glyphs on the agent color, not images.

---

## Files in this bundle

**Prototypes (open in a browser):**
- `HexaUI Prototype.html` — the interactive prototype (chat + per-agent widgets + Tweaks). Primary reference.
- `HexaUI Agent Layouts.html` — five/six full-page agent layouts.
- `HexaUI Widgets.html` — the widget library themed in HexaUI + agent-switching demos.
- `HexaUI Reference.html` — screens, foundations, components.

**Source of truth:**
- `theme.css` — all tokens, chrome, chat, motion.
- `widgets.css` — widget chrome in HexaUI tokens + prototype layout glue.
- `HexaUI Spec.md` — the written spec.

**Prototype React (Babel JSX, reference only):**
- `app.jsx`, `prototype-widgets.jsx`, `agent-layouts.jsx`, `widgets.jsx`, `widgets-agents.jsx`, `reference.jsx`, `icons.jsx`, `design-canvas.jsx`, `tweaks-panel.jsx`.

**Also reference (you already have these):** the `agent-ui` repo docs — `README.md`, `docs/widgets.md` — and the widget `.tsx` files. These define the real component APIs you're theming and configuring.

---

## Suggested build order
1. **Theme bridge** — port `theme.css` tokens into the shadcn/Tailwind layer; verify a native widget recolors via `main_color`.
2. **Host chrome shell** — sidebar (shared history + file tree) + top bar (agent picker) + composer, wrapping `<AgentUI>`.
3. **One agent end-to-end** (Probe or Atlas) — author its YAML, wire a mock dispatcher + echo bridge. Proves the look + the configure-in-YAML thesis with no backend.
4. **Restyle the two chat widgets** to the prototype design.
5. **Real bridge** — one LLM endpoint + `tool-call` streaming (the library's `examples/llm` is the template).
6. **Shared cross-agent history store**, then add the remaining agents as YAML configs.
