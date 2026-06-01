/**
 * Bridge an agent's hex `main_color` onto the chrome's accent CSS vars, so the
 * shell (outside `<AgentUI>`'s au-root) tints from the same single variable.
 * `--accent-color` is the raw hex (links, carets, glyphs); `--primary`/`--ring`
 * are HSL triplets for shadcn `bg-primary` / `ring` utilities.
 */
export function accentVars(hex: string): React.CSSProperties {
  const triplet = hexToHslTriplet(hex);
  const vars: Record<string, string> = { "--accent-color": hex };
  if (triplet) {
    vars["--primary"] = triplet;
    vars["--ring"] = triplet;
  }
  return vars as React.CSSProperties;
}

function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  let h = hex.replace("#", "");
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  if (h.length !== 6 && h.length !== 8) return null;
  const n = parseInt(h.slice(0, 6), 16);
  if (Number.isNaN(n)) return null;
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

export function hexToHslTriplet(hex: string): string | null {
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
