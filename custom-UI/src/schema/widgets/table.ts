import type { FromSchema } from "json-schema-to-ts";
import { WidgetBaseProperties } from "../widget-base.js";
import { DataSourceSchema } from "../common.js";

export const TableModeSchema = { enum: ["head", "tail"] } as const;

export const TableWidgetSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "table" },
    /** Inline CSV content. Ignored when `data_source` is set. */
    content: { type: "string" },
    /**
     * Dispatcher action returning the CSV payload as a string,
     * or `{ csv: string }`, or a 2D array of rows (`string[][]`).
     */
    data_source: DataSourceSchema,
    /** Whether to take rows from the start (`head`) or end (`tail`). */
    mode: TableModeSchema,
    /**
     * How many data rows to show. Renamed from "size" to avoid clashing with
     * the widget-base layout `size`. Defaults to 20.
     */
    rows: { type: "integer", minimum: 1, maximum: 10000 },
    /** CSV delimiter. Defaults to auto-detect among `,`, `;`, `\t`. */
    delimiter: { type: "string", minLength: 1, maxLength: 1 },
    /** Treat the first row as a header. Defaults to true. */
    has_header: { type: "boolean" },
    /** Shown when no source is configured or the payload is empty. */
    empty_text: { type: "string" },
    /** Shown while data_source is loading and no payload has arrived. */
    loading_text: { type: "string" },
  },
  required: ["name", "type", "size"],
  additionalProperties: false,
} as const;

export type TableMode = FromSchema<typeof TableModeSchema>;
export type TableWidget = FromSchema<typeof TableWidgetSchema>;
