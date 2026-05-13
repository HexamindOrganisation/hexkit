import type { WidgetProps } from "../registry/types.js";
import type { ButtonGroupWidget } from "../schema/widgets/button-group.js";
import { Button } from "../components/ui/button.js";
import { cn } from "../lib/utils.js";

export function ButtonGroupWidgetComponent({
  props,
  dispatcher,
}: WidgetProps<ButtonGroupWidget>): JSX.Element {
  const orientation = props.orientation ?? "horizontal";
  return (
    <div
      className={cn(
        "flex gap-2",
        orientation === "vertical"
          ? "flex-col items-stretch"
          : "flex-row flex-wrap items-center",
      )}
    >
      {props.buttons.map((b, i) => (
        <Button
          key={i}
          variant={b.variant ?? "default"}
          size={b.size ?? "default"}
          disabled={b.disabled ?? false}
          onClick={() => {
            void dispatcher.invoke(b.action, b.args);
          }}
        >
          {b.label}
        </Button>
      ))}
    </div>
  );
}
