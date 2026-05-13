import { useMemo } from "react";
import type { WidgetProps } from "../registry/types.js";
import type { TableWidget } from "../schema/widgets/table.js";
import { useWidgetData } from "../runtime/context.js";
import { cn } from "../lib/utils.js";

type CsvPayload = string | { csv: string } | string[][];

export function TableWidgetComponent({
  props,
}: WidgetProps<TableWidget>): JSX.Element {
  const { data, loading, error } = useWidgetData<CsvPayload>(props.data_source);

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

  if (props.data_source && error) {
    return (
      <div className="text-sm italic text-destructive">
        Failed to load table: {error.message}
      </div>
    );
  }
  if (props.data_source && loading && !data) {
    return (
      <div className="text-sm italic text-muted-foreground">
        {props.loading_text ?? "Loading table…"}
      </div>
    );
  }
  if (!sourceRows || sourceRows.length === 0) {
    return (
      <div className="text-sm italic text-muted-foreground">
        {props.empty_text ?? "No data."}
      </div>
    );
  }

  const header = hasHeader ? sourceRows[0] : null;
  const allBody = hasHeader ? sourceRows.slice(1) : sourceRows;
  const body =
    mode === "tail"
      ? allBody.slice(Math.max(0, allBody.length - limit))
      : allBody.slice(0, limit);

  const columnCount = Math.max(
    header?.length ?? 0,
    ...body.map((r) => r.length),
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-auto rounded-md border border-border">
        <table className="w-full border-collapse text-sm">
          {header && (
            <thead className="sticky top-0 z-10 bg-muted">
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
            {body.map((row, r) => (
              <tr
                key={r}
                className={cn(
                  "border-b border-border last:border-b-0",
                  r % 2 === 1 && "bg-muted/30",
                )}
              >
                {Array.from({ length: columnCount }).map((_, c) => (
                  <td
                    key={c}
                    className="px-3 py-1.5 align-top text-foreground"
                  >
                    {row[c] ?? ""}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-1 text-[0.7rem] text-muted-foreground">
        Showing {body.length} of {allBody.length} rows ({mode})
      </div>
    </div>
  );
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
