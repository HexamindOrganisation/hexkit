import type { WidgetProps } from "../registry/types.js";
import type {
  MetricFormat,
  MetricSpec,
  MetricsWidget,
} from "../schema/widgets/metrics.js";
import { useWidgetData } from "../runtime/context.js";
import { cn } from "../lib/utils.js";

type CellValue =
  | number
  | string
  | { value: number | string; delta?: number; hint?: string };

type Payload = Record<string, CellValue>;

export function MetricsWidgetComponent({
  props,
}: WidgetProps<MetricsWidget>): JSX.Element {
  const { data, loading, error } = useWidgetData<Payload>(props.data_source);

  if (props.data_source && error) {
    return (
      <div className="text-sm italic text-destructive">
        Failed to load metrics: {error.message}
      </div>
    );
  }
  if (props.data_source && loading && !data) {
    return (
      <div className="text-sm italic text-muted-foreground">
        {props.loading_text ?? "Loading metrics…"}
      </div>
    );
  }
  if (!props.data_source) {
    return (
      <div className="text-sm italic text-muted-foreground">
        {props.empty_text ?? "No data_source configured."}
      </div>
    );
  }

  const cols = props.columns;
  const gridClass = cols
    ? cols === 1
      ? "grid grid-cols-1 gap-3"
      : cols === 2
        ? "grid grid-cols-1 gap-3 sm:grid-cols-2"
        : cols === 3
          ? "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
          : cols === 4
            ? "grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4"
            : cols === 5
              ? "grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
              : "grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6"
    : "flex flex-wrap gap-3";

  return (
    <div className={cn(gridClass, "p-1")}>
      {props.metrics.map((m) => (
        <Cell key={m.id} spec={m} payload={data?.[m.id]} flex={!cols} />
      ))}
    </div>
  );
}

function Cell({
  spec,
  payload,
  flex,
}: {
  spec: MetricSpec;
  payload: CellValue | undefined;
  flex: boolean;
}): JSX.Element {
  const { rawValue, delta, hint } = unpack(payload);
  const display =
    rawValue === undefined
      ? "—"
      : formatValue(rawValue, spec.format ?? "number", {
          precision: spec.precision,
          prefix: spec.prefix,
          suffix: spec.suffix,
        });
  const finalHint = hint ?? spec.hint;

  return (
    <div
      className={cn(
        "rounded-md border border-border bg-card px-3 py-2",
        flex && "min-w-[120px] flex-1",
      )}
    >
      <div className="flex items-center gap-1.5">
        {spec.icon && (
          <img src={spec.icon} alt="" className="h-3.5 w-3.5 shrink-0" />
        )}
        <div className="text-[0.7rem] font-medium uppercase tracking-wide text-muted-foreground">
          {spec.label}
        </div>
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <div className="text-xl font-semibold leading-none text-foreground">
          {display}
        </div>
        {delta !== undefined && delta !== 0 && (
          <DeltaBadge delta={delta} />
        )}
      </div>
      {finalHint && (
        <div className="mt-1 text-xs text-muted-foreground">{finalHint}</div>
      )}
    </div>
  );
}

function DeltaBadge({ delta }: { delta: number }): JSX.Element {
  const up = delta > 0;
  const sign = up ? "▲" : "▼";
  return (
    <span
      className={cn(
        "text-xs font-medium",
        up ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400",
      )}
    >
      {sign} {Math.abs(delta).toLocaleString(undefined, {
        maximumFractionDigits: 2,
      })}
    </span>
  );
}

function unpack(value: CellValue | undefined): {
  rawValue: number | string | undefined;
  delta?: number;
  hint?: string;
} {
  if (value === undefined || value === null) return { rawValue: undefined };
  if (typeof value === "number" || typeof value === "string") {
    return { rawValue: value };
  }
  if (typeof value === "object" && "value" in value) {
    const out: { rawValue: number | string; delta?: number; hint?: string } = {
      rawValue: value.value,
    };
    if (typeof value.delta === "number") out.delta = value.delta;
    if (typeof value.hint === "string") out.hint = value.hint;
    return out;
  }
  return { rawValue: undefined };
}

function formatValue(
  raw: number | string,
  format: MetricFormat,
  opts: { precision?: number; prefix?: string; suffix?: string },
): string {
  const { prefix = "", suffix = "" } = opts;

  if (format === "string") {
    return `${prefix}${String(raw)}${suffix}`;
  }

  const n = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isFinite(n)) return `${prefix}${String(raw)}${suffix}`;

  const precision = opts.precision;

  switch (format) {
    case "percent": {
      // Treat input as a fraction (0.42 → "42%"). If already > 1, assume pre-scaled.
      const scaled = Math.abs(n) <= 1 ? n * 100 : n;
      return `${prefix}${formatNumber(scaled, precision ?? 1)}%${suffix}`;
    }
    case "currency": {
      // Default to USD; consumers can override symbol via `prefix`.
      const body = formatNumber(n, precision ?? 2);
      return prefix ? `${prefix}${body}${suffix}` : `$${body}${suffix}`;
    }
    case "duration":
      return `${prefix}${formatDuration(n)}${suffix}`;
    case "bytes":
      return `${prefix}${formatBytes(n, precision ?? 1)}${suffix}`;
    case "number":
    default:
      return `${prefix}${formatNumber(n, precision)}${suffix}`;
  }
}

function formatNumber(n: number, precision?: number): string {
  return n.toLocaleString(undefined, {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision ?? 2,
  });
}

function formatDuration(ms: number): string {
  if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`;
  if (ms < 1000) return `${formatNumber(ms, 0)}ms`;
  const s = ms / 1000;
  if (s < 60) return `${formatNumber(s, 2)}s`;
  const m = Math.floor(s / 60);
  const rs = Math.round(s - m * 60);
  if (m < 60) return `${m}m ${rs}s`;
  const h = Math.floor(m / 60);
  const rm = m - h * 60;
  return `${h}h ${rm}m`;
}

function formatBytes(bytes: number, precision: number): string {
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let i = 0;
  let n = Math.abs(bytes);
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  const sign = bytes < 0 ? "-" : "";
  return `${sign}${formatNumber(n, i === 0 ? 0 : precision)} ${units[i]}`;
}
