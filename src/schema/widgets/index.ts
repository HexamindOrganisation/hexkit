export {
  ButtonGroupWidgetSchema,
  type ButtonGroupWidget,
  ButtonGroupItemSchema,
  type ButtonGroupItem,
  ButtonVariantSchema,
  type ButtonVariant,
  ButtonSizeSchema,
  type ButtonSize,
} from "./button-group.js";
export {
  FileTreeWidgetSchema,
  type FileTreeWidget,
  FileTreeNodeSchema,
  type FileTreeNode,
  FileTreeActionSchema,
  type FileTreeAction,
} from "./file-tree.js";
export {
  PageHeaderWidgetSchema,
  type PageHeaderWidget,
} from "./page-header.js";
export {
  PageFooterWidgetSchema,
  type PageFooterWidget,
} from "./page-footer.js";
export {
  AiChatInputWidgetSchema,
  type AiChatInputWidget,
} from "./ai-chat-input.js";
export {
  AiResponseWidgetSchema,
  type AiResponseWidget,
} from "./ai-response.js";
export {
  AiHistoryWidgetSchema,
  type AiHistoryWidget,
} from "./ai-history.js";

import { ButtonGroupWidgetSchema } from "./button-group.js";
import { FileTreeWidgetSchema } from "./file-tree.js";
import { PageHeaderWidgetSchema } from "./page-header.js";
import { PageFooterWidgetSchema } from "./page-footer.js";
import { AiChatInputWidgetSchema } from "./ai-chat-input.js";
import { AiResponseWidgetSchema } from "./ai-response.js";
import { AiHistoryWidgetSchema } from "./ai-history.js";
import { z } from "zod";

export const BuiltinWidgetSchemas = {
  "button-group": ButtonGroupWidgetSchema,
  "file-tree": FileTreeWidgetSchema,
  "page-header": PageHeaderWidgetSchema,
  "page-footer": PageFooterWidgetSchema,
  "ai-chat-input": AiChatInputWidgetSchema,
  "ai-response": AiResponseWidgetSchema,
  "ai-history": AiHistoryWidgetSchema,
} as const;

export type BuiltinWidgetType = keyof typeof BuiltinWidgetSchemas;

/** Discriminated union of all built-in widgets. Extended at runtime by the registry. */
export const BuiltinWidgetUnion = z.discriminatedUnion("type", [
  ButtonGroupWidgetSchema,
  FileTreeWidgetSchema,
  PageHeaderWidgetSchema,
  PageFooterWidgetSchema,
  AiChatInputWidgetSchema,
  AiResponseWidgetSchema,
  AiHistoryWidgetSchema,
]);

export type BuiltinWidget = z.infer<typeof BuiltinWidgetUnion>;
