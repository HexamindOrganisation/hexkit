import type { FromSchema } from "json-schema-to-ts";
import { WidgetBaseProperties } from "../widget-base.js";
import { ActionSchema, DataSourceSchema } from "../common.js";

const FieldBaseProperties = {
  id: { type: "string", minLength: 1 },
  label: { type: "string", minLength: 1 },
  required: { type: "boolean" },
  help: { type: "string" },
  disabled: { type: "boolean" },
} as const;

const FieldBaseRequired = ["id", "label", "type"] as const;

const TextFieldSchema = {
  type: "object",
  properties: {
    ...FieldBaseProperties,
    type: { enum: ["text", "email", "password", "url", "search", "tel"] },
    placeholder: { type: "string" },
    default: { type: "string" },
    min_length: { type: "integer", minimum: 0 },
    max_length: { type: "integer", minimum: 1 },
    pattern: { type: "string" },
  },
  required: FieldBaseRequired,
} as const;

const TextareaFieldSchema = {
  type: "object",
  properties: {
    ...FieldBaseProperties,
    type: { const: "textarea" },
    placeholder: { type: "string" },
    default: { type: "string" },
    rows: { type: "integer", minimum: 1, maximum: 20 },
    min_length: { type: "integer", minimum: 0 },
    max_length: { type: "integer", minimum: 1 },
  },
  required: FieldBaseRequired,
} as const;

const NumberFieldSchema = {
  type: "object",
  properties: {
    ...FieldBaseProperties,
    type: { const: "number" },
    placeholder: { type: "string" },
    default: { type: "number" },
    min: { type: "number" },
    max: { type: "number" },
    step: { type: "number", exclusiveMinimum: 0 },
  },
  required: FieldBaseRequired,
} as const;

const CheckboxFieldSchema = {
  type: "object",
  properties: {
    ...FieldBaseProperties,
    type: { const: "checkbox" },
    default: { type: "boolean" },
  },
  required: FieldBaseRequired,
} as const;

const SelectOptionSchema = {
  type: "object",
  properties: {
    label: { type: "string", minLength: 1 },
    value: { type: "string", minLength: 1 },
  },
  required: ["label", "value"],
  additionalProperties: false,
} as const;

const SelectFieldSchema = {
  type: "object",
  properties: {
    ...FieldBaseProperties,
    type: { const: "select" },
    options: { type: "array", items: SelectOptionSchema, minItems: 1 },
    default: { type: "string" },
    placeholder: { type: "string" },
  },
  required: [...FieldBaseRequired, "options"],
} as const;

const RadioFieldSchema = {
  type: "object",
  properties: {
    ...FieldBaseProperties,
    type: { const: "radio" },
    options: { type: "array", items: SelectOptionSchema, minItems: 1 },
    default: { type: "string" },
  },
  required: [...FieldBaseRequired, "options"],
} as const;

const DateFieldSchema = {
  type: "object",
  properties: {
    ...FieldBaseProperties,
    type: { enum: ["date", "time", "datetime-local"] },
    default: { type: "string" },
    min: { type: "string" },
    max: { type: "string" },
  },
  required: FieldBaseRequired,
} as const;

export const FormFieldSchema = {
  oneOf: [
    TextFieldSchema,
    TextareaFieldSchema,
    NumberFieldSchema,
    CheckboxFieldSchema,
    SelectFieldSchema,
    RadioFieldSchema,
    DateFieldSchema,
  ],
} as const;

export const FormWidgetSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "form" },
    fields: {
      type: "array",
      items: FormFieldSchema,
      minItems: 1,
    },
    /** Action dispatched on submit. Receives `{ ...values }` as args. */
    submit_action: ActionSchema,
    /** Optional extra args merged into the submit payload. */
    submit_args: { type: "object", additionalProperties: true },
    submit_label: { type: "string" },
    /** If set, shows a reset button. */
    reset_label: { type: "string" },
    /** Number of columns for the field grid (1–4). Default 1. */
    columns: { type: "integer", minimum: 1, maximum: 4 },
    /** Prefill values from a dispatcher action returning a record. */
    data_source: DataSourceSchema,
    /** Message shown after a successful submit. */
    success_message: { type: "string" },
    /** Reset the form to defaults after a successful submit. */
    reset_on_success: { type: "boolean" },
  },
  required: ["name", "type", "size", "fields", "submit_action"],
  additionalProperties: false,
} as const;

export type FormField = FromSchema<typeof FormFieldSchema>;
export type FormWidget = FromSchema<typeof FormWidgetSchema>;
