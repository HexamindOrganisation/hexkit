import { PositionSchema, SizeSchema } from "./common.js";

/**
 * Properties shared by every widget. Spread into a widget schema's
 * `properties` and add the per-widget `type` const + any widget-specific
 * fields. The required base keys are listed in `WidgetBaseRequired`.
 */
export const WidgetBaseProperties = {
  name: { type: "string", minLength: 1 },
  position: PositionSchema,
  size: SizeSchema,
} as const;

export const WidgetBaseRequired = ["name", "type", "size"] as const;
