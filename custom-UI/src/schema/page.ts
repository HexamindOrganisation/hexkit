import type { FromSchema } from "json-schema-to-ts";
import { MainMenuItemSchema } from "./common.js";

/**
 * Theme is intentionally minimal: pick a curated mode + one accent color.
 * Background, foreground, borders, muted, etc. all stay at the curated
 * shadcn defaults for the chosen mode — they're tuned to work together.
 *
 * `overrides` is an escape hatch: raw CSS variable values applied inline on
 * the AgentUI root (e.g. { "--muted": "210 40% 90%" }).
 */
export const ThemeSchema = {
  type: "object",
  properties: {
    mode: { enum: ["light", "dark", "system"] },
    accent: { type: "string", pattern: "^#[0-9a-fA-F]{3,8}$" },
    overrides: {
      type: "object",
      additionalProperties: { type: "string" },
    },
  },
  additionalProperties: false,
} as const;

export const PageSchema = {
  type: "object",
  properties: {
    layout_type: { enum: ["grid", "flex", "sidebar", "tabs"] },
    theme: ThemeSchema,
    main_menu: { type: "array", items: MainMenuItemSchema },
  },
  required: ["layout_type"],
  additionalProperties: false,
} as const;

export type Theme = FromSchema<typeof ThemeSchema>;
export type Page = FromSchema<typeof PageSchema>;
