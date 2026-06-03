import type { FromSchema } from "json-schema-to-ts";
import { WidgetBaseProperties } from "../widget-base.js";
import { RefreshSchema } from "../common.js";

export const ButtonVariantSchema = {
  enum: ["default", "destructive", "outline", "secondary", "ghost", "link"],
} as const;

export const ButtonSizeSchema = {
  enum: ["default", "sm", "lg", "icon"],
} as const;

export const ButtonGroupItemSchema = {
  type: "object",
  properties: {
    label: { type: "string", minLength: 1 },
    action: { type: "string", minLength: 1 },
    args: { type: "object", additionalProperties: true },
    /** Widget names to re-pull after this action succeeds. */
    refresh: RefreshSchema,
    variant: ButtonVariantSchema,
    size: ButtonSizeSchema,
    disabled: { type: "boolean" },
  },
  required: ["label", "action"],
  additionalProperties: false,
} as const;

export const ButtonGroupWidgetSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "button-group" },
    buttons: {
      type: "array",
      items: ButtonGroupItemSchema,
      minItems: 1,
    },
    orientation: { enum: ["horizontal", "vertical"] },
  },
  required: ["name", "type", "size", "buttons"],
  additionalProperties: false,
} as const;

export type ButtonVariant = FromSchema<typeof ButtonVariantSchema>;
export type ButtonSize = FromSchema<typeof ButtonSizeSchema>;
export type ButtonGroupItem = FromSchema<typeof ButtonGroupItemSchema>;
export type ButtonGroupWidget = FromSchema<typeof ButtonGroupWidgetSchema>;
