import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  parseYaml,
  compilePlan,
  WidgetRegistry,
  builtinWidgets,
} from "../src/index.js";

const here = dirname(fileURLToPath(import.meta.url));

function loadFixture(relPath: string): string {
  return readFileSync(join(here, "fixtures", relPath), "utf8");
}

describe("pipeline", () => {
  it("parses and compiles the seed dashboard example", () => {
    const text = loadFixture("valid/dashboard.yaml");
    const parsed = parseYaml(text);
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;

    const registry = new WidgetRegistry(builtinWidgets);
    const plan = compilePlan(parsed.value.data, {
      registry,
      locate: parsed.value.locate,
    });
    expect(plan.ok).toBe(true);
    if (!plan.ok) return;

    expect(plan.value.widgets).toHaveLength(2);
    expect(plan.value.layout.kind).toBe("grid");

    if (plan.value.layout.kind === "grid") {
      // Both widgets are width 6 → they should pack into row 1 across 12 columns.
      const cells = plan.value.layout.cells;
      expect(cells).toHaveLength(2);
      expect(cells[0]!.rowStart).toBe(1);
      expect(cells[1]!.rowStart).toBe(1);
      // Horizontal bias should place "My Files" (left) at column 1 and
      // "My Tasks" (right) at column 7.
      const byId = Object.fromEntries(cells.map((c) => [c.id, c]));
      expect(byId["My Files"]!.colStart).toBe(1);
      expect(byId["My Tasks"]!.colStart).toBe(7);
    }
  });

  it("reports a diagnostic for a missing widget name", () => {
    const text = loadFixture("invalid/missing-name.yaml");
    const parsed = parseYaml(text);
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;

    const registry = new WidgetRegistry(builtinWidgets);
    const plan = compilePlan(parsed.value.data, { registry });
    expect(plan.ok).toBe(false);
    if (plan.ok) return;
    expect(plan.errors.some((d) => d.code === "resolve.missing-name")).toBe(true);
  });

  it("includes YAML source line on schema diagnostics", () => {
    // Missing layout_type.
    const yaml = `page: {}\nwidgets: []\n`;
    const parsed = parseYaml(yaml);
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    const registry = new WidgetRegistry(builtinWidgets);
    const plan = compilePlan(parsed.value.data, {
      registry,
      locate: parsed.value.locate,
    });
    expect(plan.ok).toBe(false);
    if (plan.ok) return;
    // Ajv error should surface with a source location from the page node.
    const anyLoc = plan.errors.some((d) => d.sourceLine !== undefined);
    expect(anyLoc).toBe(true);
  });

  it("marks chromeless widgets so the host can drop the default frame", () => {
    const yaml = `
page:
  layout_type: "grid"
widgets:
  - name: "header"
    type: "page-header"
    size: { width: 12, height: "auto" }
    title: "Hello"
  - name: "actions"
    type: "button-group"
    size: { width: 12, height: "auto" }
    buttons:
      - label: "Go"
        action: "go"
`;
    const parsed = parseYaml(yaml);
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    const registry = new WidgetRegistry(builtinWidgets);
    const plan = compilePlan(parsed.value.data, {
      registry,
      locate: parsed.value.locate,
    });
    expect(plan.ok).toBe(true);
    if (!plan.ok) return;

    const byName = Object.fromEntries(
      plan.value.widgets.map((w) => [w.name, w]),
    );
    expect(byName["header"]!.chromeless).toBe(true);
    expect(byName["actions"]!.chromeless).toBeUndefined();
  });
});
