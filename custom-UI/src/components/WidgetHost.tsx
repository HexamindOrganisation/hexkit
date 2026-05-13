import { Component, type ErrorInfo, type ReactNode } from "react";
import type { RenderPlanWidget } from "../compile/plan.js";
import type { ActionDispatcher } from "../runtime/dispatcher.js";
import { WidgetScope } from "../runtime/context.js";

export interface WidgetHostProps {
  widget: RenderPlanWidget;
  dispatcher: ActionDispatcher;
  style?: React.CSSProperties;
}

export function WidgetHost({
  widget,
  dispatcher,
  style,
}: WidgetHostProps): JSX.Element {
  const Component = widget.component;
  const height = widget.height === "auto" ? undefined : `${widget.height}px`;
  const className = widget.chromeless
    ? "au-widget-host au-widget-host-chromeless"
    : "au-widget-host";
  return (
    <div
      className={className}
      data-widget-name={widget.name}
      data-widget-type={widget.type}
      style={{ height, ...style }}
    >
      <WidgetScope name={widget.name}>
        <WidgetErrorBoundary widgetName={widget.name}>
          <Component
            id={widget.id}
            name={widget.name}
            props={widget.props}
            dispatcher={dispatcher}
          />
        </WidgetErrorBoundary>
      </WidgetScope>
    </div>
  );
}

interface EBState {
  error: Error | null;
}

class WidgetErrorBoundary extends Component<
  { widgetName: string; children: ReactNode },
  EBState
> {
  override state: EBState = { error: null };

  static getDerivedStateFromError(error: Error): EBState {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error(
      `[agent-ui] widget "${this.props.widgetName}" crashed:`,
      error,
      info,
    );
  }

  override render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="au-widget-error">
          Widget "{this.props.widgetName}" crashed: {this.state.error.message}
        </div>
      );
    }
    return this.props.children;
  }
}
