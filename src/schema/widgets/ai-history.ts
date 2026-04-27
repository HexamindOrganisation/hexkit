import { z } from "zod";
import { WidgetBaseShape } from "../widget-base.js";
import { ActionSchema, DataSourceSchema } from "../common.js";

export const ConversationSummarySchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  preview: z.string().optional(),
  timestamp: z.number().optional(),
});

export type ConversationSummary = z.infer<typeof ConversationSummarySchema>;

export const AiHistoryWidgetSchema = z.object({
  ...WidgetBaseShape,
  type: z.literal("ai-history"),
  /** Returns ConversationSummary[]. Provided by the host. */
  data_source: DataSourceSchema.optional(),
  /** Static fallback if no data_source is set. */
  conversations: z.array(ConversationSummarySchema).optional(),
  /**
   * Action invoked with `{ id }` when a conversation is clicked.
   * Must return ConversationMessage[] (or { messages: ConversationMessage[] }).
   * The result is loaded into the conversation log and rendered by ai-response.
   */
  on_select: ActionSchema,
  empty_text: z.string().optional(),
});

export type AiHistoryWidget = z.infer<typeof AiHistoryWidgetSchema>;
