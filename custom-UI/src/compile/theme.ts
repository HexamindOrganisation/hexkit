import type { Page } from "../schema/page.js";

/**
 * Theme inputs — both the YAML `page.theme` block and the `<AgentUI theme>`
 * prop accept this shape. Curated palette per `mode`; one `accent`; raw
 * CSS-var `overrides` as an escape hatch.
 */
export interface ThemeTokens {
  mode?: "light" | "dark" | "system";
  /** Hex color (`#RGB`, `#RRGGBB`, `#RRGGBBAA`). Bridges to `--primary`, `--ring`, `--primary-foreground`. */
  accent?: string;
  /**
   * Raw CSS custom property overrides written inline on the AgentUI root.
   * Values are verbatim — for shadcn variables, pass HSL triplets like
   * `"210 40% 90%"` (consumed via `hsl(var(--name))`).
   */
  overrides?: Record<string, string>;
}

export type ResolvedTheme = {
  /** Resolved mode. `"system"` is preserved here; the shell listens to
   *  `prefers-color-scheme` to decide which class to apply at render time. */
  mode: "light" | "dark" | "system";
  /** Inline CSS custom properties to set on the AgentUI root. */
  cssVars: Record<string, string>;
};

export function resolveTheme(
  page: Page,
  override: Partial<ThemeTokens> = {},
): ResolvedTheme {
  const theme = page.theme;
  const mode = override.mode ?? theme?.mode ?? "light";
  // `page.main_color` is the active agent's color — the single variable that
  // recolors the page. It wins over `theme.accent`; an explicit override wins
  // over both.
  const accent = override.accent ?? page.main_color ?? theme?.accent;

  const cssVars: Record<string, string> = {};

  if (accent) {
    const hsl = hexToHsl(accent);
    if (hsl) {
      cssVars["--primary"] = hsl;
      cssVars["--ring"] = hsl;
      // The agent color is the only color: tints links, focus rings, the
      // streaming caret, metric deltas, tool dots. Widgets read it via
      // `--accent-color` (a raw hex) where shadcn's HSL `--accent` (a neutral
      // hover surface) would be wrong.
      cssVars["--accent-color"] = accent;
      const fgHsl = hexToHsl(contrastFg(accent));
      if (fgHsl) cssVars["--primary-foreground"] = fgHsl;
    }
  }

  // Caller-supplied raw overrides take precedence.
  const overrides = { ...theme?.overrides, ...override.overrides };
  for (const [name, value] of Object.entries(overrides)) {
    cssVars[name] = value;
  }

  return { mode, cssVars };
}

function contrastFg(hex: string): string {
  const rgb = hexToRgb(hex);
  if (!rgb) return "#ffffff";
  const lum = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
  return lum > 0.6 ? "#0a0a0a" : "#ffffff";
}

function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  let h = hex.replace("#", "");
  if (h.length === 3) {
    h = h
      .split("")
      .map((c) => c + c)
      .join("");
  }
  if (h.length !== 6 && h.length !== 8) return null;
  const n = parseInt(h.slice(0, 6), 16);
  if (Number.isNaN(n)) return null;
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

/**
 * Convert a hex color to the `H S% L%` triplet shadcn variables expect
 * (e.g. `199 73% 41%`). Returns null if the input isn't a valid hex.
 */
function hexToHsl(hex: string): string | null {
  const rgb = hexToRgb(hex);
  if (!rgb) return null;
  const r = rgb.r / 255;
  const g = rgb.g / 255;
  const b = rgb.b / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let h = 0;
  let s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
    else if (max === g) h = ((b - r) / d + 2) / 6;
    else h = ((r - g) / d + 4) / 6;
  }
  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}
