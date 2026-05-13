import type { FromSchema } from "json-schema-to-ts";
import { WidgetBaseProperties } from "../widget-base.js";

export const AiResponseWidgetSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "ai-response" },
    empty_text: { type: "string" },
    thinking_indicator: { enum: ["dots", "text", "none"] },
    thinking_text: { type: "string" },
    responding_text: { type: "string" },
  },
  required: ["name", "type", "size"],
  additionalProperties: false,
} as const;

export type AiResponseWidget = FromSchema<typeof AiResponseWidgetSchema>;
