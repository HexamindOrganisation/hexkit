import type { WidgetProps } from "../registry/types.js";
import type { MarkdownWidget } from "../schema/widgets/markdown.js";
import { useWidgetData } from "../runtime/context.js";
import { renderMarkdown } from "../lib/markdown.js";

export function MarkdownWidgetComponent({
  props,
}: WidgetProps<MarkdownWidget>): JSX.Element {
  const { data, loading, error } = useWidgetData<string>(props.data_source);

  const source = props.data_source
    ? typeof data === "string"
      ? data
      : ""
    : props.content ?? "";

  if (props.data_source && loading && !data) {
    return (
      <div className="text-sm italic text-muted-foreground">
        {props.empty_text ?? "Loading…"}
      </div>
    );
  }
  if (error) {
    return (
      <div className="text-sm italic text-destructive">
        Failed to load markdown: {error.message}
      </div>
    );
  }
  if (!source) {
    return (
      <div className="text-sm italic text-muted-foreground">
        {props.empty_text ?? ""}
      </div>
    );
  }

  return (
    <div className="prose prose-sm max-w-none text-sm leading-relaxed text-foreground">
      {renderMarkdown(source)}
    </div>
  );
}
