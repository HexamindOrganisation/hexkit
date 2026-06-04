import type { FromSchema } from "json-schema-to-ts";

export const IconSchema = { type: "string" } as const;
export const ActionSchema = { type: "string", minLength: 1 } as const;

/**
 * Widget names whose `data_source` should re-pull after an action succeeds.
 * The YAML is the only layer that knows widget names — the backend stays
 * UI-agnostic; it just exposes data via actions, and this wires which display
 * widgets refresh when an action changes their underlying data.
 */
export const RefreshSchema = {
  type: "array",
  items: { type: "string", minLength: 1 },
} as const;

export const PositionSchema = {
  type: "object",
  properties: {
    horizontal: { enum: ["left", "right", "center"] },
    vertical: { enum: ["high", "low", "middle"] },
  },
  additionalProperties: false,
} as const;

export const SizeSchema = {
  type: "object",
  properties: {
    width: { type: "integer", minimum: 1, maximum: 12 },
    height: {
      oneOf: [
        { type: "number", exclusiveMinimum: 0 },
        { const: "auto" },
      ],
    },
  },
  required: ["width", "height"],
  additionalProperties: false,
} as const;

export const DataSourceSchema = {
  type: "object",
  properties: {
    action: ActionSchema,
    args: { type: "object", additionalProperties: true },
    subscribe: { type: "boolean" },
  },
  required: ["action"],
  additionalProperties: false,
} as const;

export type Position = FromSchema<typeof PositionSchema>;
export type Size = FromSchema<typeof SizeSchema>;
export type DataSource = FromSchema<typeof DataSourceSchema>;
