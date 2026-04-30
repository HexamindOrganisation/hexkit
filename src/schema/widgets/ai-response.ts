import { z } from "zod";
import { WidgetBaseShape } from "../widget-base.js";

export const AiResponseWidgetSchema = z.object({
  ...WidgetBaseShape,
  type: z.literal("ai-response"),
  empty_text: z.string().optional(),
  thinking_indicator: z.enum(["dots", "text", "none"]).optional(),
  thinking_text: z.string().optional(),
  responding_text: z.string().optional(),
});

export type AiResponseWidget = z.infer<typeof AiResponseWidgetSchema>;
