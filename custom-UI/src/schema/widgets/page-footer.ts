import type { FromSchema } from "json-schema-to-ts";
import { WidgetBaseProperties } from "../widget-base.js";

export const PageFooterWidgetSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "page-footer" },
    text: { type: "string" },
  },
  required: ["name", "type", "size"],
  additionalProperties: false,
} as const;

export type PageFooterWidget = FromSchema<typeof PageFooterWidgetSchema>;
