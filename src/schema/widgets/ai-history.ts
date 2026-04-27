import { z } from "zod";
import { WidgetBaseShape } from "../widget-base.js";

export const AiHistoryWidgetSchema = z.object({
  ...WidgetBaseShape,
  type: z.literal("ai-history"),
  empty_text: z.string().optional(),
  show_system: z.boolean().optional(),
});

export type AiHistoryWidget = z.infer<typeof AiHistoryWidgetSchema>;
