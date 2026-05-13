import { describe, it, expect } from "vitest";
import { WidgetRegistry, builtinWidgets, compilePlan } from "../src/index.js";

describe("widget schema coverage", () => {
  it("validates a config with every built-in widget type", () => {
    const registry = new WidgetRegistry(builtinWidgets);
    const config = {
      page: {
        layout_type: "grid" as const,
        theme: { mode: "dark" as const, accent: "#ff0066" },
      },
      widgets: [
        {
          name: "hdr",
          type: "page-header",
          size: { width: 12, height: 80 },
          title: "Dashboard",
        },
        {
          name: "btns",
          type: "button-group",
          size: { width: 6, height: 60 },
          buttons: [{ label: "Refresh", action: "refresh" }],
        },
        {
          name: "tree",
          type: "file-tree",
          size: { width: 4, height: 400 },
          nodes: [
            {
              id: "root",
              name: "root",
              type: "folder",
              children: [
                { id: "f", name: "file.txt", type: "file", size: 12 },
              ],
            },
          ],
        },
        {
          name: "md",
          type: "markdown",
          size: { width: 8, height: 200 },
          content: "# hi",
        },
        {
          name: "frm",
          type: "form",
          size: { width: 6, height: 300 },
          submit_action: "submit",
          fields: [
            { id: "email", label: "Email", type: "email" },
            { id: "msg", label: "Message", type: "textarea", rows: 5 },
            { id: "agree", label: "Agree", type: "checkbox" },
            {
              id: "color",
              label: "Color",
              type: "select",
              options: [{ label: "Red", value: "red" }],
            },
          ],
        },
        {
          name: "mtr",
          type: "metrics",
          size: { width: 12, height: 100 },
          metrics: [{ id: "total", label: "Total", format: "number" }],
        },
        {
          name: "tbl",
          type: "table",
          size: { width: 12, height: 300 },
          content: "a,b\n1,2",
          mode: "head",
          rows: 10,
        },
        {
          name: "spc",
          type: "spacer",
          size: { width: 12, height: 20 },
        },
        {
          name: "chat",
          type: "ai-chat-input",
          size: { width: 12, height: 80 },
          rows: 3,
        },
        {
          name: "rsp",
          type: "ai-response",
          size: { width: 12, height: 200 },
          thinking_indicator: "dots",
        },
        {
          name: "hist",
          type: "ai-history",
          size: { width: 4, height: 400 },
          on_select: "load_conv",
        },
        {
          name: "ftr",
          type: "page-footer",
          size: { width: 12, height: 40 },
          text: "v1",
        },
      ],
    };
    const plan = compilePlan(config, { registry });
    if (!plan.ok) {
      // Surface diagnostics on failure for easier debugging.
      // eslint-disable-next-line no-console
      console.error(plan.errors);
    }
    expect(plan.ok).toBe(true);
    if (!plan.ok) return;
    // 11 main-slot widgets + 1 footer-slot widget (page-footer)
    expect(plan.value.widgets).toHaveLength(11);
    expect(plan.value.footer).toHaveLength(1);
  });

  it("rejects an invalid form field discriminator", () => {
    const registry = new WidgetRegistry(builtinWidgets);
    const config = {
      page: { layout_type: "flex" as const },
      widgets: [
        {
          name: "frm",
          type: "form",
          size: { width: 6, height: 200 },
          submit_action: "submit",
          fields: [
            { id: "x", label: "X", type: "not-a-field-type" },
          ],
        },
      ],
    };
    const plan = compilePlan(config, { registry });
    expect(plan.ok).toBe(false);
  });

  it("rejects a file-tree node with bad shape (recursive $ref)", () => {
    const registry = new WidgetRegistry(builtinWidgets);
    const config = {
      page: { layout_type: "flex" as const },
      widgets: [
        {
          name: "tree",
          type: "file-tree",
          size: { width: 6, height: 300 },
          nodes: [
            {
              id: "root",
              name: "root",
              type: "folder",
              children: [{ id: "kid", type: "file" /* missing name */ }],
            },
          ],
        },
      ],
    };
    const plan = compilePlan(config, { registry });
    expect(plan.ok).toBe(false);
  });
});
