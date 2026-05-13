import { PageSchema, type Page } from "./page.js";
import { BuiltinWidgetUnion, type BuiltinWidget } from "./widgets/index.js";

export * from "./common.js";
export * from "./page.js";
export * from "./widget-base.js";
export * from "./widgets/index.js";

/**
 * Root config schema with only the built-in widgets. For host-defined
 * widgets, build a registry-aware schema via `buildConfigSchema(registry)`.
 */
export const ConfigSchema = {
  type: "object",
  properties: {
    page: PageSchema,
    widgets: { type: "array", items: BuiltinWidgetUnion },
  },
  required: ["page"],
  additionalProperties: false,
} as const;

export interface Config {
  page: Page;
  widgets?: BuiltinWidget[];
}

/**
 * Construct a Config JSON Schema with a dynamically-assembled `widgets` union
 * that includes custom widgets from the host registry. Each input must be a
 * JSON Schema object.
 */
export function buildConfigSchema(widgetSchemas: readonly object[]): object {
  const items =
    widgetSchemas.length === 0
      ? { type: "object", additionalProperties: true }
      : widgetSchemas.length === 1
        ? widgetSchemas[0]!
        : { oneOf: [...widgetSchemas] };
  return {
    type: "object",
    properties: {
      page: PageSchema,
      widgets: { type: "array", items },
    },
    required: ["page"],
    additionalProperties: false,
  };
}
