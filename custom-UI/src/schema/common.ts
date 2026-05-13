import type { FromSchema } from "json-schema-to-ts";

export const IconSchema = { type: "string" } as const;
export const ActionSchema = { type: "string", minLength: 1 } as const;

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

export const MainMenuItemSchema = {
  type: "object",
  properties: {
    name: { type: "string", minLength: 1 },
    icon: IconSchema,
    action: ActionSchema,
  },
  required: ["name", "action"],
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
export type MainMenuItem = FromSchema<typeof MainMenuItemSchema>;
export type DataSource = FromSchema<typeof DataSourceSchema>;
