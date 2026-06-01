# HexaUI — Design & Widget Spec

> A living spec for the HexaUI platform: a multi-agent chat product whose
> per-agent UI is assembled by developers from configurable widgets, on top
> of one constant, minimalist chrome. This document captures the decisions we
> made together and points to the files that embody them.

---

## 1. What HexaUI is

A single chat platform that hosts **many agents**. Each agent has a distinct
job (operations, research, code, finance, monitoring, integrations) and the
developer who owns that agent configures its UI in **YAML** — picking and
arranging template **widgets**. The platform ships the widgets pre-styled, so
the look is unified and "already done"; developers compose, they don't style.

Three layers:

1. **Chrome** — the persistent shell. Never agent-configured.
2. **Main widgets** — the agent-configured region, authored per agent in YAML.
3. **Agent identity** — the active agent is the *only* color in the product.

### Files

| File | Role |
|---|---|
| `HexaUI Prototype.html` | The interactive prototype — live chat + per-agent widgets + Tweaks |
| `HexaUI Reference.html` | Static reference: screens, foundations, components |
| `HexaUI Widgets.html` | The widget library, restyled in the HexaUI language + agent-switching |
| `HexaUI Agent Layouts.html` | Five full-page, real-use-case agent layouts |
| `theme.css` | The design system — tokens, chrome, chat, motion |
| `widgets.css` | Widget chrome in HexaUI tokens + prototype layout glue |
| `app.jsx` | Prototype application |
| `prototype-widgets.jsx` | Per-agent MAIN-widget layouts for the prototype |
| `agent-layouts.jsx` | The five static showcase layouts |
| `widgets.jsx`, `widgets-agents.jsx`, `reference.jsx`, `icons.jsx` | Specimen + helper components |

---

## 2. Visual language

Editorial / neutral. Warm-neutral greys (the Claude/ChatGPT family), a
transitional serif for display, a quiet grotesk for UI, mono for data.
Reduced chrome — hairlines and surfaces, not boxes and shadows.

### Type

- **UI / body:** Hanken Grotesk
- **Display / greeting / long-form answers:** Source Serif 4 (Libre Baskerville / Newsreader selectable)
- **Data / code / identifiers / labels:** IBM Plex Mono
- Body never below ~14px; greeting ~42–47px; uppercase micro-labels at 11–11.5px.

### Color — the neutral scale (dark)

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#1e1e1f` | Canvas |
| `--bg-2` | `#181819` | Sidebar / code |
| `--surface` | `#282829` | Input · cards |
| `--surface-2` | `#323234` | Hover |
| `--surface-3` | `#3d3d40` | Pressed |
| `--text` | `#ecedef` | Primary text |
| `--text-2` | `#a3a6ac` | Secondary |
| `--text-3` | `#6e7177` | Tertiary / icons |
| `--line` / `--line-2` | 10% / 5.5% white | Hairlines |

A matching **light** scale exists; chrome stays neutral in both. Semantic
tones for widgets: `--ok` (sage), `--danger` (rose), `--warn` (amber).

### Form

- Radii: `--r-sm 7` · `--r-md 11` · `--r-lg 16` · `--r-pill`
- One elevation token (`--shadow`) — used only on the composer and floating menus. Everything else is flat, separated by hairlines.
- Density: comfortable (default) / compact, both token-driven.

---

## 3. The agent IS the accent  ★ core principle

Chrome is monochrome end-to-end. The **only** color in the product is the
active agent's signature hue. It tints the avatar, the send button, focus
rings, links, the hero rule, metric deltas, tool-call status dots, and the
streaming caret.

### The roster

| Agent | Role | Color |
|---|---|---|
| Atlas | Operations copilot | `#4f74c9` (blue) |
| Probe | Research & retrieval | `#3f9d94` (teal) |
| Forge | Code & build | `#56809e` (slate-blue) |
| Sentry | Monitoring & safety | `#c79a52` (amber) |
| Ledger | Finance operations | `#c2788f` (pink) |
| Relay | Integrations & RPA | `#c07a55` (terracotta) |

### Mechanism

The whole product recolors from **one variable**. In the widget library
(shadcn/Tailwind) this is `page.main_color`; in the prototype it is the
`--accent` custom property. Set it per agent and every widget re-tints at
once — no per-widget overrides.

```yaml
page:
  layout_type: "grid"
  main_color: "#3f9d94"   # ← the active agent's color; recolors the whole page
```

### How a switch feels

The recolor is instant under the hood; transform-only motion makes it
legible and calm:

- **Accent bloom** — a soft blur of the new color blooms behind the avatar as it settles (~0.6s).
- **Avatar settle / breathe** — the glyph scales in and breathes a faint ring while idle; pulses harder while thinking.
- **Identity swap** — top-bar glyph + name adopt the new agent.
- **Seeded intent** — the chat placeholder, suggestion chips, and the MAIN widget set change per agent.
- **Thinking color** — the composing metaball, status shimmer, and caret all render in the agent accent.

---

## 4. Chrome — the persistent shell (NOT widgets)

These are constant across every agent and are **not** agent-configured widgets:

- **Agent identity / top bar** — the agent picker (avatar + name), session title, and global actions. (The standalone `page-header` widget was dropped — identity lives in the shell.)
- **Conversation history** — **shared across all agents.** Regardless of which agent is selected, the user sees every conversation from every agent and can switch between them. Each row is prefixed with its agent's colored glyph so ownership is obvious. Selecting a conversation switches to its agent, loads the chat, and swaps in that agent's widget layout. Uses the prototype's sidebar history directly.
- **File tree** — the workspace (repository, statements, documents, connectors — labeled per agent).
- **Chat composer** (`ai-chat-input`) and **transcript** (`ai-response`) — see §6. These use the prototype design verbatim and are constant.

---

## 5. The chat — prototype design (constant)

The conversation is the spine of every layout and never changes shape.

- **User turns** — right-aligned, bordered card (`.ucard`).
- **Assistant turns** — avatar + name + an accent tick + timestamp, then prose; may include code blocks and copy / regenerate actions. No bubble — prose sits on the canvas.
- **Thinking** — a liquid metaball loader under a shimmering status line, avatar pulsing in the agent color.
- **Streaming** — answer types in character-by-character, trailing a block caret in the agent color.
- **Composer** — one quiet field: attach on the left, voice + send on the right. **No agent selector in the input** (the picker lives in the top bar). Send dims until there's text, then lights to the agent color; the border picks up the accent on focus.

---

## 6. Widget catalog

Every visible thing in the agent-configured region is a widget. shadcn/Tailwind
tokens map straight onto the HexaUI scale, so styling is inherited:

```
background → --bg     card/popover → --surface   muted → --surface-2 / --bg-2
border → --line       foreground → --text         muted-fg → --text-2 / --text-3
primary/accent → --accent (= agent color)          destructive → --danger
radius → --r-md
```

### Main widgets (agent-configured)

| `type` | Purpose | Notes |
|---|---|---|
| `metrics` | Stat-card strip | Tabular figures, uppercase micro-label, sage/rose delta badge; live via `subscribe` |
| `table` | Scrollable CSV | Sticky uppercase header, hairline zebra rows, mono numerics, "showing N of M" foot |
| `markdown` | Safe rich text | Serif headings, accent-underlined links, mono code chips |
| `button-group` | Action row | 6 shadcn variants; only the primary action carries the agent fill |
| `form` | Schema-driven input | Fields on the canvas tone; required markers + focus in the accent; submit is the only filled control |
| `tool-calls` | Live invocation log | Status dot: amber running → accent done → rose error; expandable mono JSON |
| `ai-response` | Transcript | Prototype design (constant) |
| `ai-chat-input` | Composer | Prototype design (constant) |
| `spacer` | Layout reservation | Invisible |
| `page-footer` | Footer band | Muted, pinned |

### Chrome widgets (side menu — not agent-configured)

`file-tree` (workspace) and conversation history. `page-header` was removed.

---

## 7. Layout examples — real use cases

Each agent's developer authors a layout fit to the job. The chrome and chat
stay constant; the MAIN region differs. (See `HexaUI Agent Layouts.html`.)

| Agent | Use case | MAIN layout |
|---|---|---|
| **Atlas** | Incident response console | SLO **metrics** strip on top · transcript · live **tool-calls** trace panel |
| **Forge** | Coding workspace | Repo **file-tree** in the menu · PR/CI **action bar** · transcript · **tool-calls** |
| **Ledger** | Reconciliation | Finance **metrics** · invoice **table** as the lead · transcript as a side rail |
| **Probe** | Research desk | History-led · transcript · cited **Sources** (markdown) panel |
| **Relay** | Integration builder | Configuration **form** · transcript |
| **Sentry** | Monitoring | Fleet **metrics** · recent-audits **tool-calls** |

### In the prototype

`prototype-widgets.jsx` defines `window.AgentWidgets[agentId] = { top, side, sideTitle, sideWidth }`. The prototype renders `top` above and `side` beside the centered chat; both inherit `--accent`, and the tool-call panels show a live "running" row while the agent is thinking. Widgets appear once a conversation is active (the greeting stays clean).

---

## 8. Open / future

- **Per-agent dashboard landing** before the first message (currently the greeting stays clean; widgets appear in-conversation).
- **Live YAML → preview** so a developer can paste a config and watch it render.
- Custom widgets beyond the native set (the library supports `defineWidget`).

---

*Tweakable in the prototype: theme (dark/light), accent mode (agent / mono /
blue / sage), density, sidebar, and hero typeface.*
