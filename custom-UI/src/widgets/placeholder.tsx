import type { WidgetProps } from "../registry/types.js";

export interface PlaceholderProps {
  name: string;
  type: string;
  reason: string;
}

export function PlaceholderWidget({
  props,
}: WidgetProps<PlaceholderProps>): JSX.Element {
  return (
    <div className="au-widget-placeholder">
      <div className="au-widget-placeholder-title">
        {props.name}
      </div>
      <div className="au-widget-placeholder-body">
        unregistered type: <code>{props.type}</code>
        {props.reason && <> — {props.reason}</>}
      </div>
    </div>
  );
}
