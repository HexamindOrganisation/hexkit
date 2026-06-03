import { useCallback, useEffect, useMemo, useState } from "react";
import type { WidgetProps } from "../registry/types.js";
import type {
  FormField,
  FormWidget,
} from "../schema/widgets/form.js";
import { useAgentUIContext, useWidgetData } from "../runtime/context.js";
import { Button } from "../components/ui/button.js";
import { Input } from "../components/ui/input.js";
import { Textarea } from "../components/ui/textarea.js";
import { cn } from "../lib/utils.js";

type FormValues = Record<string, string | number | boolean>;

export function FormWidgetComponent({
  props,
}: WidgetProps<FormWidget>): JSX.Element {
  const { dispatcher, requestRefresh } = useAgentUIContext();
  const { data: prefill } = useWidgetData<Record<string, unknown>>(
    props.data_source,
  );

  const defaults = useMemo<FormValues>(
    () => buildDefaults(props.fields, prefill),
    [props.fields, prefill],
  );

  const [values, setValues] = useState<FormValues>(defaults);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<
    | { kind: "idle" }
    | { kind: "success"; message: string }
    | { kind: "error"; message: string }
  >({ kind: "idle" });

  // Re-seed when defaults change (prefill arrives or schema changes).
  useEffect(() => {
    setValues(defaults);
  }, [defaults]);

  const setValue = useCallback((id: string, v: string | number | boolean) => {
    setValues((prev) => ({ ...prev, [id]: v }));
    setErrors((prev) => {
      if (!prev[id]) return prev;
      const { [id]: _, ...rest } = prev;
      return rest;
    });
    setStatus({ kind: "idle" });
  }, []);

  const reset = useCallback(() => {
    setValues(defaults);
    setErrors({});
    setStatus({ kind: "idle" });
  }, [defaults]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validation = validate(props.fields, values);
    if (Object.keys(validation).length > 0) {
      setErrors(validation);
      setStatus({ kind: "idle" });
      return;
    }
    setErrors({});
    setSubmitting(true);
    try {
      await dispatcher.invoke(props.submit_action, {
        ...(props.submit_args ?? {}),
        ...values,
      });
      if (props.refresh?.length) requestRefresh(props.refresh);
      setStatus({
        kind: "success",
        message: props.success_message ?? "Submitted.",
      });
      if (props.reset_on_success) reset();
    } catch (err) {
      setStatus({
        kind: "error",
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setSubmitting(false);
    }
  };

  const cols = props.columns ?? 1;
  const gridClass =
    cols === 1
      ? "grid grid-cols-1 gap-3"
      : cols === 2
        ? "grid grid-cols-1 gap-3 sm:grid-cols-2"
        : cols === 3
          ? "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
          : "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4";

  return (
    <form className="flex flex-col gap-4 p-1" onSubmit={onSubmit} noValidate>
      <div className={gridClass}>
        {props.fields.map((field) => (
          <Field
            key={field.id}
            field={field}
            value={values[field.id]}
            error={errors[field.id]}
            disabled={submitting || field.disabled === true}
            onChange={(v) => setValue(field.id, v)}
          />
        ))}
      </div>

      <div className="flex items-center gap-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Submitting…" : props.submit_label ?? "Submit"}
        </Button>
        {props.reset_label && (
          <Button
            type="button"
            variant="ghost"
            onClick={reset}
            disabled={submitting}
          >
            {props.reset_label}
          </Button>
        )}
        {status.kind === "success" && (
          <span className="text-xs text-muted-foreground">{status.message}</span>
        )}
        {status.kind === "error" && (
          <span className="text-xs text-destructive">{status.message}</span>
        )}
      </div>
    </form>
  );
}

function Field({
  field,
  value,
  error,
  disabled,
  onChange,
}: {
  field: FormField;
  value: string | number | boolean | undefined;
  error?: string;
  disabled: boolean;
  onChange: (v: string | number | boolean) => void;
}): JSX.Element {
  const labelEl = (
    <label
      htmlFor={field.id}
      className="flex items-center gap-1 text-sm font-medium text-foreground"
    >
      {field.label}
      {field.required && <span className="text-destructive">*</span>}
    </label>
  );
  const helpEl = field.help ? (
    <p className="text-xs text-muted-foreground">{field.help}</p>
  ) : null;
  const errorEl = error ? (
    <p className="text-xs text-destructive">{error}</p>
  ) : null;
  const wrap = (control: JSX.Element) => (
    <div className="flex flex-col gap-1">
      {labelEl}
      {control}
      {errorEl ?? helpEl}
    </div>
  );

  switch (field.type) {
    case "textarea":
      return wrap(
        <Textarea
          id={field.id}
          rows={field.rows ?? 3}
          placeholder={field.placeholder}
          value={(value as string) ?? ""}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={!!error}
        />,
      );

    case "number":
      return wrap(
        <Input
          id={field.id}
          type="number"
          placeholder={field.placeholder}
          value={value === undefined || value === "" ? "" : String(value)}
          disabled={disabled}
          min={field.min}
          max={field.max}
          step={field.step}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === "") {
              onChange("");
              return;
            }
            const n = Number(raw);
            onChange(Number.isNaN(n) ? raw : n);
          }}
          aria-invalid={!!error}
        />,
      );

    case "checkbox": {
      // Inline layout: checkbox + label on one row.
      return (
        <div className="flex flex-col gap-1">
          <label className="flex items-center gap-2 text-sm font-medium text-foreground">
            <input
              id={field.id}
              type="checkbox"
              checked={value === true}
              disabled={disabled}
              onChange={(e) => onChange(e.target.checked)}
              className="h-4 w-4 rounded border-input accent-primary"
              aria-invalid={!!error}
            />
            <span>
              {field.label}
              {field.required && <span className="text-destructive"> *</span>}
            </span>
          </label>
          {errorEl ?? helpEl}
        </div>
      );
    }

    case "select":
      return wrap(
        <select
          id={field.id}
          value={(value as string) ?? ""}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={!!error}
          className={cn(
            "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          {field.placeholder !== undefined && (
            <option value="" disabled>
              {field.placeholder}
            </option>
          )}
          {field.options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>,
      );

    case "radio":
      return (
        <div className="flex flex-col gap-1">
          {labelEl}
          <div className="flex flex-col gap-1.5">
            {field.options.map((o) => (
              <label
                key={o.value}
                className="flex items-center gap-2 text-sm text-foreground"
              >
                <input
                  type="radio"
                  name={field.id}
                  value={o.value}
                  checked={value === o.value}
                  disabled={disabled}
                  onChange={() => onChange(o.value)}
                  className="h-4 w-4 accent-primary"
                />
                <span>{o.label}</span>
              </label>
            ))}
          </div>
          {errorEl ?? helpEl}
        </div>
      );

    case "date":
    case "time":
    case "datetime-local":
      return wrap(
        <Input
          id={field.id}
          type={field.type}
          value={(value as string) ?? ""}
          disabled={disabled}
          min={field.min}
          max={field.max}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={!!error}
        />,
      );

    // text-like
    default:
      return wrap(
        <Input
          id={field.id}
          type={field.type}
          placeholder={field.placeholder}
          value={(value as string) ?? ""}
          disabled={disabled}
          minLength={field.min_length}
          maxLength={field.max_length}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={!!error}
        />,
      );
  }
}

function buildDefaults(
  fields: FormField[],
  prefill?: Record<string, unknown>,
): FormValues {
  const out: FormValues = {};
  for (const f of fields) {
    const fromPrefill = prefill?.[f.id];
    if (fromPrefill !== undefined && fromPrefill !== null) {
      // Accept string/number/boolean prefill values as-is; coerce others to string.
      if (
        typeof fromPrefill === "string" ||
        typeof fromPrefill === "number" ||
        typeof fromPrefill === "boolean"
      ) {
        out[f.id] = fromPrefill;
        continue;
      }
      out[f.id] = String(fromPrefill);
      continue;
    }
    if ("default" in f && f.default !== undefined) {
      out[f.id] = f.default;
      continue;
    }
    out[f.id] = f.type === "checkbox" ? false : "";
  }
  return out;
}

function validate(
  fields: FormField[],
  values: FormValues,
): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const f of fields) {
    const v = values[f.id];
    const empty =
      v === undefined ||
      v === "" ||
      (f.type === "checkbox" && v === false && f.required === true);

    if (f.required && empty && f.type !== "checkbox") {
      errors[f.id] = "Required.";
      continue;
    }
    if (f.type === "checkbox" && f.required && v !== true) {
      errors[f.id] = "Required.";
      continue;
    }

    if (empty) continue;

    if (
      (f.type === "text" ||
        f.type === "email" ||
        f.type === "password" ||
        f.type === "url" ||
        f.type === "search" ||
        f.type === "tel" ||
        f.type === "textarea") &&
      typeof v === "string"
    ) {
      if (f.min_length !== undefined && v.length < f.min_length) {
        errors[f.id] = `Must be at least ${f.min_length} characters.`;
        continue;
      }
      if (f.max_length !== undefined && v.length > f.max_length) {
        errors[f.id] = `Must be at most ${f.max_length} characters.`;
        continue;
      }
    }

    if (f.type === "email" && typeof v === "string" && !/^\S+@\S+\.\S+$/.test(v)) {
      errors[f.id] = "Enter a valid email.";
      continue;
    }
    if (f.type === "url" && typeof v === "string") {
      try {
        new URL(v);
      } catch {
        errors[f.id] = "Enter a valid URL.";
        continue;
      }
    }
    if (
      (f.type === "text" ||
        f.type === "email" ||
        f.type === "password" ||
        f.type === "url" ||
        f.type === "search" ||
        f.type === "tel") &&
      f.pattern &&
      typeof v === "string"
    ) {
      try {
        if (!new RegExp(f.pattern).test(v)) {
          errors[f.id] = "Invalid format.";
          continue;
        }
      } catch {
        // ignore bad regex from config
      }
    }
    if (f.type === "number") {
      if (typeof v !== "number" || Number.isNaN(v)) {
        errors[f.id] = "Enter a number.";
        continue;
      }
      if (f.min !== undefined && v < f.min) {
        errors[f.id] = `Must be ≥ ${f.min}.`;
        continue;
      }
      if (f.max !== undefined && v > f.max) {
        errors[f.id] = `Must be ≤ ${f.max}.`;
        continue;
      }
    }
  }
  return errors;
}
