import { z } from "zod";
import { MainMenuItemSchema } from "./common.js";

/**
 * Theme is intentionally minimal: pick a curated mode + one accent color.
 * Background, foreground, borders, muted, etc. all stay at the curated
 * shadcn defaults for the chosen mode — they're tuned to work together.
 *
 * `overrides` is an escape hatch: raw CSS variable values applied inline on
 * the AgentUI root (e.g. { "--muted": "210 40% 90%" }).
 */
export const ThemeSchema = z.object({
  mode: z.enum(["light", "dark", "system"]).optional(),
  accent: z
    .string()
    .regex(/^#[0-9a-fA-F]{3,8}$/, "accent must be a hex color")
    .optional(),
  overrides: z.record(z.string()).optional(),
});

export const PageSchema = z.object({
  layout_type: z.enum(["grid", "flex", "sidebar", "tabs"]),
  theme: ThemeSchema.optional(),
  /** Sidebar-layout menu items. Ignored by other layouts. */
  main_menu: z.array(MainMenuItemSchema).optional(),
});

export type Page = z.infer<typeof PageSchema>;
export type Theme = z.infer<typeof ThemeSchema>;
