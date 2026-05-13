import type { FromSchema } from "json-schema-to-ts";
import { WidgetBaseProperties } from "../widget-base.js";
import { DataSourceSchema } from "../common.js";

export const MarkdownWidgetSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "markdown" },
    /** Inline markdown content. Mutually exclusive with `data_source`. */
    content: { type: "string" },
    /** Fetch markdown text dynamically; the resolved value must be a string. */
    data_source: DataSourceSchema,
    /** Text shown while loading or when content is empty. */
    empty_text: { type: "string" },
  },
  required: ["name", "type", "size"],
  additionalProperties: false,
} as const;

export type MarkdownWidget = FromSchema<typeof MarkdownWidgetSchema>;
