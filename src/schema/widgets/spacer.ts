import { z } from "zod";
import { WidgetBaseShape } from "../widget-base.js";

/**
 * An empty widget. Renders nothing — exists so authors can reserve a
 * cell in the layout to create space between other widgets.
 */
export const SpacerWidgetSchema = z.object({
  ...WidgetBaseShape,
  type: z.literal("spacer"),
});

export type SpacerWidget = z.infer<typeof SpacerWidgetSchema>;
