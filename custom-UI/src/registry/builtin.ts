import { defineWidget } from "./register.js";
import {
  ButtonGroupWidgetSchema,
  type ButtonGroupWidget,
  FileTreeWidgetSchema,
  type FileTreeWidget,
  PageHeaderWidgetSchema,
  type PageHeaderWidget,
  PageFooterWidgetSchema,
  type PageFooterWidget,
  AiChatInputWidgetSchema,
  type AiChatInputWidget,
  AiResponseWidgetSchema,
  type AiResponseWidget,
  AiHistoryWidgetSchema,
  type AiHistoryWidget,
  SpacerWidgetSchema,
  type SpacerWidget,
  MarkdownWidgetSchema,
  type MarkdownWidget,
  FormWidgetSchema,
  type FormWidget,
  MetricsWidgetSchema,
  type MetricsWidget,
  TableWidgetSchema,
  type TableWidget,
  ToolCallsWidgetSchema,
  type ToolCallsWidget,
} from "../schema/widgets/index.js";
import { ButtonGroupWidgetComponent } from "../widgets/button-group.js";
import { FileTreeWidgetComponent } from "../widgets/file-tree.js";
import { PageHeaderWidgetComponent } from "../widgets/page-header.js";
import { PageFooterWidgetComponent } from "../widgets/page-footer.js";
import { AiChatInputWidgetComponent } from "../widgets/ai-chat-input.js";
import { AiResponseWidgetComponent } from "../widgets/ai-response.js";
import { AiHistoryWidgetComponent } from "../widgets/ai-history.js";
import { SpacerWidgetComponent } from "../widgets/spacer.js";
import { MarkdownWidgetComponent } from "../widgets/markdown.js";
import { FormWidgetComponent } from "../widgets/form.js";
import { MetricsWidgetComponent } from "../widgets/metrics.js";
import { TableWidgetComponent } from "../widgets/table.js";
import { ToolCallsWidgetComponent } from "../widgets/tool-calls.js";
import type { AnyWidgetDefinition } from "./types.js";

export const builtinWidgets: AnyWidgetDefinition[] = [
  defineWidget<ButtonGroupWidget>({
    type: "button-group",
    schema: ButtonGroupWidgetSchema,
    component: ButtonGroupWidgetComponent,
  }),
  defineWidget<FileTreeWidget>({
    type: "file-tree",
    schema: FileTreeWidgetSchema,
    component: FileTreeWidgetComponent,
  }),
  defineWidget<PageHeaderWidget>({
    type: "page-header",
    schema: PageHeaderWidgetSchema,
    component: PageHeaderWidgetComponent,
    chromeless: true,
  }),
  defineWidget<PageFooterWidget>({
    type: "page-footer",
    schema: PageFooterWidgetSchema,
    component: PageFooterWidgetComponent,
    chromeless: true,
    slot: "footer",
  }),
  defineWidget<AiChatInputWidget>({
    type: "ai-chat-input",
    schema: AiChatInputWidgetSchema,
    component: AiChatInputWidgetComponent,
    chromeless: true,
    // HexaUI: the composer is constant chrome pinned to the bottom of the chat
    // area (the transcript scrolls above it), not a widget in the content flow.
    slot: "footer",
  }),
  defineWidget<AiResponseWidget>({
    type: "ai-response",
    schema: AiResponseWidgetSchema,
    component: AiResponseWidgetComponent,
    chromeless: true,
  }),
  defineWidget<AiHistoryWidget>({
    type: "ai-history",
    schema: AiHistoryWidgetSchema,
    component: AiHistoryWidgetComponent,
    chromeless: true,
  }),
  defineWidget<SpacerWidget>({
    type: "spacer",
    schema: SpacerWidgetSchema,
    component: SpacerWidgetComponent,
    chromeless: true,
  }),
  defineWidget<MarkdownWidget>({
    type: "markdown",
    schema: MarkdownWidgetSchema,
    component: MarkdownWidgetComponent,
  }),
  defineWidget<FormWidget>({
    type: "form",
    schema: FormWidgetSchema,
    component: FormWidgetComponent,
  }),
  defineWidget<MetricsWidget>({
    type: "metrics",
    schema: MetricsWidgetSchema,
    component: MetricsWidgetComponent,
  }),
  defineWidget<TableWidget>({
    type: "table",
    schema: TableWidgetSchema,
    component: TableWidgetComponent,
  }),
  defineWidget<ToolCallsWidget>({
    type: "tool-calls",
    schema: ToolCallsWidgetSchema,
    component: ToolCallsWidgetComponent,
  }),
];
