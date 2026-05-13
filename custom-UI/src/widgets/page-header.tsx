import type { WidgetProps } from "../registry/types.js";
import type { PageHeaderWidget } from "../schema/widgets/page-header.js";

export function PageHeaderWidgetComponent({
  props,
}: WidgetProps<PageHeaderWidget>): JSX.Element {
  return (
    <header className="flex items-center gap-4 py-1">
      {props.icon && (
        <img src={props.icon} alt="" className="h-8 w-8 shrink-0" />
      )}
      <div className="flex flex-col gap-0.5">
        <h1 className="m-0 text-2xl font-semibold leading-tight tracking-tight text-foreground">
          {props.title}
        </h1>
        {props.subtitle && (
          <p className="m-0 text-sm text-muted-foreground">
            {props.subtitle}
          </p>
        )}
      </div>
    </header>
  );
}
