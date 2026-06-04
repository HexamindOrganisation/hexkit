import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve as pathResolve } from "node:path";
import {
  WidgetRegistry,
  builtinWidgets,
  parseYaml,
  compilePlan,
} from "../src/index.js";

const examples = [
  "examples/llm/config.yaml",
  "examples/minimal/config.yaml",
  "examples/layouts/flex.yaml",
  "examples/layouts/grid.yaml",
];

describe("example configs", () => {
  for (const path of examples) {
    it(`compiles ${path}`, () => {
      const text = readFileSync(pathResolve(path), "utf8");
      const parsed = parseYaml(text);
      expect(parsed.ok).toBe(true);
      if (!parsed.ok) return;
      const registry = new WidgetRegistry(builtinWidgets);
      const plan = compilePlan(parsed.value.data, {
        registry,
        locate: parsed.value.locate,
      });
      if (!plan.ok) {
        // eslint-disable-next-line no-console
        console.error(`Diagnostics for ${path}:`, plan.errors);
      }
      expect(plan.ok).toBe(true);
    });
  }
});
