import type { ResolvedWidget } from "../resolve.js";
import type { Diagnostic } from "../../diagnostics/types.js";
import type { GridCell, GridTemplate, LayoutPlan } from "./types.js";

const COLUMNS = 12;

/**
 * Greedy top-down / left-right packer with position bias.
 * - `position.horizontal: left|center|right` biases column choice.
 * - `position.vertical: high|middle|low` biases row choice via sort order.
 * - Emits a `grid-collision` diagnostic only when a widget overflows the grid.
 *
 * The packer fills one row at a time; within a row it honors the horizontal
 * bias by trying preferred columns first, falling back to the next free slot.
 */
export function compileGrid(
  widgets: ResolvedWidget[],
  diagnostics: Diagnostic[],
): Extract<LayoutPlan, { kind: "grid" }> {
  const cells: GridCell[] = [];

  // Sort by vertical bias: high → middle → low, stable within equal bias.
  const verticalRank = (w: ResolvedWidget): number => {
    const v = w.position?.vertical;
    if (v === "high") return 0;
    if (v === "middle") return 1;
    if (v === "low") return 2;
    return 1;
  };
  const sorted = [...widgets].sort(
    (a, b) => verticalRank(a) - verticalRank(b),
  );

  // Row state: which columns are taken at each row index.
  const rowFill: boolean[][] = [];
  const ensureRow = (r: number): boolean[] => {
    while (rowFill.length <= r) rowFill.push(new Array(COLUMNS).fill(false));
    return rowFill[r]!;
  };

  let maxRow = 0;

  for (const w of sorted) {
    const span = Math.min(COLUMNS, Math.max(1, w.size.width));
    if (span > COLUMNS) {
      diagnostics.push({
        severity: "error",
        code: "layout.grid-overflow",
        message: `widget "${w.name}" width ${w.size.width} exceeds 12 columns`,
        path: ["widgets", w.name, "size", "width"],
      });
      continue;
    }

    // Find (row, col) that fits span.
    const preferredCols = preferredColumns(w.position?.horizontal, span);
    let placed = false;
    let r = 0;
    while (!placed) {
      const row = ensureRow(r);
      for (const start of preferredCols) {
        if (fits(row, start, span)) {
          for (let c = start; c < start + span; c++) row[c] = true;
          cells.push({
            id: w.name,
            kind: "widget",
            colStart: start + 1, // CSS grid is 1-indexed
            colSpan: span,
            rowStart: r + 1,
            rowSpan: 1,
            height: w.size.height,
          });
          if (r > maxRow) maxRow = r;
          placed = true;
          break;
        }
      }
      if (!placed) r++;
      if (r > 512) {
        diagnostics.push({
          severity: "error",
          code: "layout.grid-collision",
          message: `could not place widget "${w.name}" after 512 rows`,
          path: ["widgets", w.name],
        });
        break;
      }
    }
  }

  const template: GridTemplate = {
    columns: COLUMNS,
    rows: Math.max(1, maxRow + 1),
    gap: "var(--au-space-5)",
  };

  return {
    kind: "grid",
    template,
    cells,
  };
}

function preferredColumns(
  horizontal: "left" | "right" | "center" | undefined,
  span: number,
): number[] {
  const starts: number[] = [];
  for (let s = 0; s + span <= COLUMNS; s++) starts.push(s);
  if (horizontal === "left") return starts;
  if (horizontal === "right") return [...starts].reverse();
  if (horizontal === "center") {
    const midStart = Math.max(0, Math.floor((COLUMNS - span) / 2));
    return [...starts].sort(
      (a, b) => Math.abs(a - midStart) - Math.abs(b - midStart),
    );
  }
  return starts;
}

function fits(row: boolean[], start: number, span: number): boolean {
  if (start + span > COLUMNS) return false;
  for (let c = start; c < start + span; c++) {
    if (row[c]) return false;
  }
  return true;
}
