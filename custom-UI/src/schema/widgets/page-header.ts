import type { FromSchema } from "json-schema-to-ts";
import { WidgetBaseProperties } from "../widget-base.js";
import { IconSchema } from "../common.js";

export const PageHeaderWidgetSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "page-header" },
    title: { type: "string", minLength: 1 },
    subtitle: { type: "string" },
    icon: IconSchema,
  },
  required: ["name", "type", "size", "title"],
  additionalProperties: false,
} as const;

export type PageHeaderWidget = FromSchema<typeof PageHeaderWidgetSchema>;
