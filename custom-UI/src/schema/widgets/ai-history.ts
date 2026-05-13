import type { FromSchema } from "json-schema-to-ts";
import { WidgetBaseProperties } from "../widget-base.js";
import { ActionSchema, DataSourceSchema } from "../common.js";

export const ConversationSummarySchema = {
  type: "object",
  properties: {
    id: { type: "string", minLength: 1 },
    title: { type: "string", minLength: 1 },
    preview: { type: "string" },
    timestamp: { type: "number" },
  },
  required: ["id", "title"],
  additionalProperties: false,
} as const;

export type ConversationSummary = FromSchema<typeof ConversationSummarySchema>;

export const AiHistoryWidgetSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "ai-history" },
    data_source: DataSourceSchema,
    conversations: { type: "array", items: ConversationSummarySchema },
    on_select: ActionSchema,
    on_new_chat: ActionSchema,
    empty_text: { type: "string" },
  },
  required: ["name", "type", "size", "on_select"],
  additionalProperties: false,
} as const;

export type AiHistoryWidget = FromSchema<typeof AiHistoryWidgetSchema>;
