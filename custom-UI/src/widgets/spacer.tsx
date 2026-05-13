import type { WidgetProps } from "../registry/types.js";
import type { SpacerWidget } from "../schema/widgets/spacer.js";

export function SpacerWidgetComponent(
  _props: WidgetProps<SpacerWidget>,
): JSX.Element {
  return <div aria-hidden="true" />;
}
