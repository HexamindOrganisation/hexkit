import type { FromSchema } from "json-schema-to-ts";
import { WidgetBaseProperties } from "../widget-base.js";

/**
 * An empty widget. Renders nothing — exists so authors can reserve a
 * cell in the layout to create space between other widgets.
 */
export const SpacerWidgetSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "spacer" },
  },
  required: ["name", "type", "size"],
  additionalProperties: false,
} as const;

export type SpacerWidget = FromSchema<typeof SpacerWidgetSchema>;
