import { z } from "zod";
import { WidgetBaseShape } from "../widget-base.js";
import { ActionSchema, DataSourceSchema } from "../common.js";

const FieldBase = {
  id: z.string().min(1).describe("Key in the submitted payload"),
  label: z.string().min(1),
  required: z.boolean().optional(),
  help: z.string().optional(),
  disabled: z.boolean().optional(),
};

const TextFieldSchema = z.object({
  ...FieldBase,
  type: z.enum(["text", "email", "password", "url", "search", "tel"]),
  placeholder: z.string().optional(),
  default: z.string().optional(),
  min_length: z.number().int().min(0).optional(),
  max_length: z.number().int().min(1).optional(),
  pattern: z.string().optional().describe("RegExp source applied to the value"),
});

const TextareaFieldSchema = z.object({
  ...FieldBase,
  type: z.literal("textarea"),
  placeholder: z.string().optional(),
  default: z.string().optional(),
  rows: z.number().int().min(1).max(20).optional(),
  min_length: z.number().int().min(0).optional(),
  max_length: z.number().int().min(1).optional(),
});

const NumberFieldSchema = z.object({
  ...FieldBase,
  type: z.literal("number"),
  placeholder: z.string().optional(),
  default: z.number().optional(),
  min: z.number().optional(),
  max: z.number().optional(),
  step: z.number().positive().optional(),
});

const CheckboxFieldSchema = z.object({
  ...FieldBase,
  type: z.literal("checkbox"),
  default: z.boolean().optional(),
});

const SelectOptionSchema = z.object({
  label: z.string().min(1),
  value: z.string().min(1),
});

const SelectFieldSchema = z.object({
  ...FieldBase,
  type: z.literal("select"),
  options: z.array(SelectOptionSchema).min(1),
  default: z.string().optional(),
  placeholder: z.string().optional(),
});

const RadioFieldSchema = z.object({
  ...FieldBase,
  type: z.literal("radio"),
  options: z.array(SelectOptionSchema).min(1),
  default: z.string().optional(),
});

const DateFieldSchema = z.object({
  ...FieldBase,
  type: z.enum(["date", "time", "datetime-local"]),
  default: z.string().optional(),
  min: z.string().optional(),
  max: z.string().optional(),
});

export const FormFieldSchema = z.discriminatedUnion("type", [
  TextFieldSchema,
  TextareaFieldSchema,
  NumberFieldSchema,
  CheckboxFieldSchema,
  SelectFieldSchema,
  RadioFieldSchema,
  DateFieldSchema,
]);

export const FormWidgetSchema = z.object({
  ...WidgetBaseShape,
  type: z.literal("form"),
  fields: z.array(FormFieldSchema).min(1),
  /** Action dispatched on submit. Receives `{ ...values }` as args. */
  submit_action: ActionSchema,
  /** Optional extra args merged into the submit payload. */
  submit_args: z.record(z.unknown()).optional(),
  submit_label: z.string().optional(),
  reset_label: z.string().optional().describe("If set, shows a reset button"),
  /** Number of columns for the field grid (1–4). Default 1. */
  columns: z.number().int().min(1).max(4).optional(),
  /** Prefill values from a dispatcher action returning a record. */
  data_source: DataSourceSchema.optional(),
  /** Message shown after a successful submit. */
  success_message: z.string().optional(),
  /** Reset the form to defaults after a successful submit. */
  reset_on_success: z.boolean().optional(),
});

export type FormField = z.infer<typeof FormFieldSchema>;
export type FormWidget = z.infer<typeof FormWidgetSchema>;
