export type ContainerSlot = "user-input" | "agent-response";

export interface GridCell {
  /** Widget `name` or a container slot id. */
  id: string;
  kind: "widget" | "container";
  colStart: number;
  colSpan: number;
  rowStart: number;
  rowSpan: number;
  height: number | "auto";
}

export interface GridTemplate {
  columns: number;
  rows: number;
  gap: string;
}

export interface FlexItem {
  id: string;
  kind: "widget" | "container";
  basis: string;
  height: number | "auto";
}

export type LayoutPlan =
  | { kind: "grid"; template: GridTemplate; cells: GridCell[] }
  | {
      kind: "flex";
      direction: "row" | "column";
      items: FlexItem[];
    };
