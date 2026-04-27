import { defineWidget } from "./register.js";
import {
  ButtonGroupWidgetSchema,
  FileTreeWidgetSchema,
  PageHeaderWidgetSchema,
  PageFooterWidgetSchema,
  AiChatInputWidgetSchema,
  AiResponseWidgetSchema,
  AiHistoryWidgetSchema,
} from "../schema/widgets/index.js";
import { ButtonGroupWidgetComponent } from "../widgets/button-group.js";
import { FileTreeWidgetComponent } from "../widgets/file-tree.js";
import { PageHeaderWidgetComponent } from "../widgets/page-header.js";
import { PageFooterWidgetComponent } from "../widgets/page-footer.js";
import { AiChatInputWidgetComponent } from "../widgets/ai-chat-input.js";
import { AiResponseWidgetComponent } from "../widgets/ai-response.js";
import { AiHistoryWidgetComponent } from "../widgets/ai-history.js";
import type { AnyWidgetDefinition } from "./types.js";

export const builtinWidgets: AnyWidgetDefinition[] = [
  defineWidget({
    type: "button-group",
    schema: ButtonGroupWidgetSchema,
    component: ButtonGroupWidgetComponent,
  }),
  defineWidget({
    type: "file-tree",
    schema: FileTreeWidgetSchema,
    component: FileTreeWidgetComponent,
  }),
  defineWidget({
    type: "page-header",
    schema: PageHeaderWidgetSchema,
    component: PageHeaderWidgetComponent,
    chromeless: true,
  }),
  defineWidget({
    type: "page-footer",
    schema: PageFooterWidgetSchema,
    component: PageFooterWidgetComponent,
    chromeless: true,
  }),
  defineWidget({
    type: "ai-chat-input",
    schema: AiChatInputWidgetSchema,
    component: AiChatInputWidgetComponent,
    chromeless: true,
  }),
  defineWidget({
    type: "ai-response",
    schema: AiResponseWidgetSchema,
    component: AiResponseWidgetComponent,
    chromeless: true,
  }),
  defineWidget({
    type: "ai-history",
    schema: AiHistoryWidgetSchema,
    component: AiHistoryWidgetComponent,
    chromeless: true,
  }),
];
