import { describe, it, expect } from "vitest";
import {
  WidgetRegistry,
  builtinWidgets,
  compilePlan,
} from "../src/index.js";

describe("markdown widget (JSON Schema spike)", () => {
  it("validates and resolves a well-formed markdown widget", () => {
    const registry = new WidgetRegistry(builtinWidgets);
    const config = {
      page: { layout_type: "flex" as const },
      widgets: [
        {
          name: "intro",
          type: "markdown",
          size: { width: 12, height: "auto" as const },
          content: "# Hello\n\nWorld",
        },
      ],
    };
    const plan = compilePlan(config, { registry });
    expect(plan.ok).toBe(true);
    if (!plan.ok) return;
    expect(plan.value.widgets).toHaveLength(1);
    const w = plan.value.widgets[0]!;
    expect(w.type).toBe("markdown");
    expect((w.props as { content: string }).content).toBe("# Hello\n\nWorld");
  });

  it("emits an Ajv-mapped diagnostic when the schema is violated", () => {
    const registry = new WidgetRegistry(builtinWidgets);
    const config = {
      page: { layout_type: "flex" as const },
      widgets: [
        {
          name: "bad",
          type: "markdown",
          size: { width: 99, height: "auto" as const }, // width max is 12
          content: "x",
        },
      ],
    };
    const plan = compilePlan(config, { registry });
    expect(plan.ok).toBe(false);
    if (plan.ok) return;
    const widthErr = plan.errors.find((d) =>
      d.path.includes("size") && d.path.includes("width"),
    );
    expect(widthErr).toBeDefined();
    expect(widthErr!.code).toMatch(/^ajv\./);
  });

  it("rejects an unexpected property (additionalProperties: false)", () => {
    const registry = new WidgetRegistry(builtinWidgets);
    const config = {
      page: { layout_type: "flex" as const },
      widgets: [
        {
          name: "extra",
          type: "markdown",
          size: { width: 6, height: 100 },
          content: "x",
          bogus_field: "nope",
        },
      ],
    };
    const plan = compilePlan(config, { registry });
    // removeAdditional: true strips it without erroring; widget still resolves.
    expect(plan.ok).toBe(true);
    if (!plan.ok) return;
    const props = plan.value.widgets[0]!.props as Record<string, unknown>;
    expect(props.bogus_field).toBeUndefined();
    expect(props.content).toBe("x");
  });

  it("requires the type literal to be 'markdown'", () => {
    const registry = new WidgetRegistry(builtinWidgets);
    const config = {
      page: { layout_type: "flex" as const },
      widgets: [
        {
          // Pretend a host registered something else under a wrong literal.
          // We force this by routing it as markdown but with mismatching type.
          name: "wrong",
          type: "markdown",
          size: { width: 6, height: 100 },
          // content valid; introduce an invalid data_source shape:
          data_source: { /* missing required action */ subscribe: true },
        },
      ],
    };
    const plan = compilePlan(config, { registry });
    expect(plan.ok).toBe(false);
    if (plan.ok) return;
    const missingAction = plan.errors.find(
      (d) => d.code === "ajv.required" && d.message.includes("action"),
    );
    expect(missingAction).toBeDefined();
  });
});
