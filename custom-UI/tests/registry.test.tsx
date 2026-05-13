import { describe, it, expect } from "vitest";
import {
  WidgetRegistry,
  builtinWidgets,
  defineWidget,
  compilePlan,
  type WidgetProps,
} from "../src/index.js";
import { WidgetBaseProperties } from "../src/schema/widget-base.js";

type BannerProps = {
  name: string;
  type: "banner";
  size: { width: number; height: number | "auto" };
  message: string;
};

function Banner({ props }: WidgetProps<BannerProps>): JSX.Element {
  return <div>{props.message}</div>;
}

describe("widget registry", () => {
  it("accepts a custom widget type end-to-end", () => {
    const CustomSchema = {
      type: "object",
      properties: {
        ...WidgetBaseProperties,
        type: { const: "banner" },
        message: { type: "string" },
      },
      required: ["name", "type", "size", "message"],
      additionalProperties: false,
    } as const;

    const registry = new WidgetRegistry([
      ...builtinWidgets,
      defineWidget<BannerProps>({
        type: "banner",
        schema: CustomSchema,
        component: Banner,
      }),
    ]);

    const config = {
      page: { layout_type: "flex" as const },
      widgets: [
        {
          name: "hero",
          type: "banner",
          size: { width: 12, height: "auto" as const },
          message: "Hello",
        },
      ],
    };

    const plan = compilePlan(config, { registry });
    expect(plan.ok).toBe(true);
    if (!plan.ok) return;
    expect(plan.value.widgets).toHaveLength(1);
    expect(plan.value.widgets[0]!.type).toBe("banner");
  });

  it("renders a placeholder for unknown widget types rather than dropping silently", () => {
    const registry = new WidgetRegistry(builtinWidgets);
    const config = {
      page: { layout_type: "grid" as const },
      widgets: [
        {
          name: "mystery",
          type: "not-a-real-type",
          size: { width: 6, height: 100 },
        },
      ],
    };
    const plan = compilePlan(config, { registry });
    expect(plan.ok).toBe(true);
    if (!plan.ok) return;
    // Per spec §11: unknown widget types render a placeholder widget.
    expect(plan.value.widgets).toHaveLength(1);
    expect(plan.value.widgets[0]!.type).toBe("not-a-real-type");
  });
});
