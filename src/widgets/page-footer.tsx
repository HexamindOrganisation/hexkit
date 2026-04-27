import type { WidgetProps } from "../registry/types.js";
import type { PageFooterWidget } from "../schema/widgets/page-footer.js";

export function PageFooterWidgetComponent({
  props,
}: WidgetProps<PageFooterWidget>): JSX.Element {
  return (
    <footer className="flex items-center justify-center px-4 py-3 text-xs text-muted-foreground">
      {props.text ?? ""}
    </footer>
  );
}
