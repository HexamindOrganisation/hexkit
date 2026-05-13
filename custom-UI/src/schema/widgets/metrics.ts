import type { FromSchema } from "json-schema-to-ts";
import { WidgetBaseProperties } from "../widget-base.js";
import { DataSourceSchema, IconSchema } from "../common.js";

export const MetricFormatSchema = {
  enum: ["number", "percent", "currency", "duration", "bytes", "string"],
} as const;

export const MetricSpecSchema = {
  type: "object",
  properties: {
    /** Key looked up in the data_source payload. */
    id: { type: "string", minLength: 1 },
    label: { type: "string", minLength: 1 },
    format: MetricFormatSchema,
    /** Decimal places for numeric formats. */
    precision: { type: "integer", minimum: 0, maximum: 10 },
    /** Prepended to the formatted value (e.g. "$"). */
    prefix: { type: "string" },
    /** Appended to the formatted value (e.g. " req/s"). */
    suffix: { type: "string" },
    /** Optional muted line under the value. Overridden by payload `hint`. */
    hint: { type: "string" },
    icon: IconSchema,
  },
  required: ["id", "label"],
  additionalProperties: false,
} as const;

export const MetricsWidgetSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "metrics" },
    metrics: {
      type: "array",
      items: MetricSpecSchema,
      minItems: 1,
    },
    /**
     * Dispatcher action returning a record keyed by each metric's `id`.
     * If `subscribe: true` and the dispatcher supports it, values update live.
     */
    data_source: DataSourceSchema,
    /** Number of columns on wide screens (1–6). Otherwise flex-wraps. */
    columns: { type: "integer", minimum: 1, maximum: 6 },
    /** Shown while data_source is loading and no payload has arrived. */
    loading_text: { type: "string" },
    /** Shown when there is no data_source or the payload is empty. */
    empty_text: { type: "string" },
  },
  required: ["name", "type", "size", "metrics"],
  additionalProperties: false,
} as const;

export type MetricFormat = FromSchema<typeof MetricFormatSchema>;
export type MetricSpec = FromSchema<typeof MetricSpecSchema>;
export type MetricsWidget = FromSchema<typeof MetricsWidgetSchema>;
