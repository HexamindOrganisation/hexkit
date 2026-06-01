import { describe, it, expect } from "vitest";
import {
  parseYaml,
  compilePlan,
  WidgetRegistry,
  builtinWidgets,
} from "../src/index.js";

function compile(yaml: string) {
  const parsed = parseYaml(yaml);
  if (!parsed.ok) throw new Error("parse failed");
  const registry = new WidgetRegistry(builtinWidgets);
  return compilePlan(parsed.value.data, { registry });
}

describe("page.main_color theme bridge", () => {
  it("drives --primary / --ring / --accent-color from main_color", () => {
    const plan = compile(`
page:
  layout_type: "grid"
  main_color: "#3f9d94"
widgets:
  - name: "t"
    type: "ai-response"
    size: { width: 12, height: "auto" }
`);
    expect(plan.ok).toBe(true);
    if (!plan.ok) return;
    const v = plan.value.theme.cssVars;
    // Hex flows through verbatim for raw-color consumers (caret, links, dots).
    expect(v["--accent-color"]).toBe("#3f9d94");
    // And as an HSL triplet for the shadcn tokens.
    expect(v["--primary"]).toBeDefined();
    expect(v["--ring"]).toBe(v["--primary"]);
    expect(v["--primary"]).not.toContain("#");
  });

  it("main_color wins over theme.accent", () => {
    const plan = compile(`
page:
  layout_type: "grid"
  main_color: "#c79a52"
  theme: { accent: "#4f74c9" }
widgets:
  - name: "t"
    type: "ai-response"
    size: { width: 12, height: "auto" }
`);
    expect(plan.ok).toBe(true);
    if (!plan.ok) return;
    expect(plan.value.theme.cssVars["--accent-color"]).toBe("#c79a52");
  });
});
