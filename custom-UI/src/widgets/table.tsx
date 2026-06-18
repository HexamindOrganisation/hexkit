import { useMemo, useState } from "react";
import type { WidgetProps } from "../registry/types.js";
import type { TableWidget } from "../schema/widgets/table.js";
import { useWidgetData } from "../runtime/context.js";
import { ContextCard } from "../lib/context-card.js";
import { cn } from "../lib/utils.js";

type CsvPayload = string | { csv: string } | string[][];

export function TableWidgetComponent({
  props,
  name,
}: WidgetProps<TableWidget>): JSX.Element {
  const { data, loading, error, refresh } = useWidgetData<CsvPayload>(props.data_source);
  // One-shot spin on click — a visible cue even when the re-pull is instant
  // (the data lives in-process). A genuine slow load shows the looping spin.
  const [clickSpin, setClickSpin] = useState(false);

  const limit = props.rows ?? 20;
  const mode = props.mode ?? "head";
  const hasHeader = props.has_header ?? true;

  const sourceRows = useMemo<string[][] | null>(() => {
    if (props.data_source) {
      if (data === undefined) return null;
      return coerceToRows(data, props.delimiter);
    }
    if (props.content !== undefined) {
      return parseCsv(props.content, props.delimiter ?? detectDelimiter(props.content));
    }
    return null;
  }, [data, props.data_source, props.content, props.delimiter]);

  // Full data (all rows) serialized as CSV — what the context toggle forwards.
  const contextText =
    sourceRows && sourceRows.length > 0 ? toCsv(sourceRows) : "";

  let body: JSX.Element;
  if (props.data_source && error) {
    body = (
      <div className="text-sm italic text-destructive">
        Failed to load table: {error.message}
      </div>
    );
  } else if (props.data_source && loading && !data) {
    body = (
      <div className="text-sm italic text-muted-foreground">
        {props.loading_text ?? "Loading table…"}
      </div>
    );
  } else if (!sourceRows || sourceRows.length === 0) {
    body = (
      <div className="text-sm italic text-muted-foreground">
        {props.empty_text ?? "No data."}
      </div>
    );
  } else {
    const header = hasHeader ? sourceRows[0] : null;
    const allBody = hasHeader ? sourceRows.slice(1) : sourceRows;
    const shown =
      mode === "tail"
        ? allBody.slice(Math.max(0, allBody.length - limit))
        : allBody.slice(0, limit);
    const columnCount = Math.max(
      header?.length ?? 0,
      ...shown.map((r) => r.length),
    );
    body = (
      <div className="flex flex-col">
        <div className="max-h-[360px] overflow-auto rounded-md border border-border">
          <table className="w-full border-collapse text-sm">
            {header && (
              <thead className="sticky top-0 bg-muted">
                <tr>
                  {Array.from({ length: columnCount }).map((_, c) => (
                    <th
                      key={c}
                      className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground"
                    >
                      {header[c] ?? ""}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {shown.map((row, r) => (
                <tr
                  key={r}
                  className={cn(
                    "border-b border-border last:border-b-0",
                    r % 2 === 1 && "bg-muted/30",
                  )}
                >
                  {Array.from({ length: columnCount }).map((_, c) => (
                    <td key={c} className="px-3 py-1.5 align-top text-foreground">
                      {row[c] ?? ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-1 text-[0.7rem] text-muted-foreground">
          Showing {shown.length} of {allBody.length} rows ({mode})
        </div>
      </div>
    );
  }

  return (
    <ContextCard
      widgetKey={name}
      caption={props.caption ?? name}
      mime="text/csv"
      text={contextText}
      headerAction={
        props.refreshable && props.data_source ? (
          <button
            type="button"
            onClick={() => {
              setClickSpin(true);
              refresh();
            }}
            disabled={loading}
            title="Refresh"
            aria-label="Refresh table"
            className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-transform hover:bg-muted hover:text-foreground active:scale-90 disabled:opacity-50"
          >
            <RefreshIcon
              className={loading ? "hx-spin-loop" : clickSpin ? "hx-spin-once" : undefined}
              onAnimationEnd={() => setClickSpin(false)}
            />
          </button>
        ) : undefined
      }
    >
      {body}
    </ContextCard>
  );
}

function RefreshIcon({
  className,
  onAnimationEnd,
}: {
  className?: string;
  onAnimationEnd?: () => void;
}): JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={className}
      onAnimationEnd={onAnimationEnd}
      style={{ width: 15, height: 15 }}
    >
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <path d="M21 3v6h-6" />
    </svg>
  );
}

/** Serialize rows back to CSV (RFC-4180-ish quoting) for the context payload. */
function toCsv(rows: string[][]): string {
  return rows
    .map((r) => r.map((cell) => csvCell(String(cell ?? ""))).join(","))
    .join("\n");
}
function csvCell(s: string): string {
  return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function coerceToRows(
  payload: CsvPayload,
  delimiter: string | undefined,
): string[][] {
  if (typeof payload === "string") {
    return parseCsv(payload, delimiter ?? detectDelimiter(payload));
  }
  if (Array.isArray(payload)) {
    return payload.map((row) => row.map((cell) => String(cell ?? "")));
  }
  if (payload && typeof payload === "object" && typeof payload.csv === "string") {
    return parseCsv(payload.csv, delimiter ?? detectDelimiter(payload.csv));
  }
  return [];
}

function detectDelimiter(text: string): string {
  const sample = text.slice(0, 4096);
  const candidates = [",", ";", "\t", "|"];
  let best = ",";
  let bestCount = -1;
  for (const d of candidates) {
    const count = countOutsideQuotes(sample, d);
    if (count > bestCount) {
      bestCount = count;
      best = d;
    }
  }
  return best;
}

function countOutsideQuotes(text: string, ch: string): number {
  let n = 0;
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (inQuotes && text[i + 1] === '"') {
        i++;
        continue;
      }
      inQuotes = !inQuotes;
      continue;
    }
    if (!inQuotes && c === ch) n++;
  }
  return n;
}

function parseCsv(text: string, delimiter: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 2;
          continue;
        }
        inQuotes = false;
        i++;
        continue;
      }
      field += ch;
      i++;
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
      i++;
      continue;
    }
    if (ch === delimiter) {
      row.push(field);
      field = "";
      i++;
      continue;
    }
    if (ch === "\r") {
      i++;
      continue;
    }
    if (ch === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      i++;
      continue;
    }
    field += ch;
    i++;
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}
