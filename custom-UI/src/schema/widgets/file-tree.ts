import type { FromSchema } from "json-schema-to-ts";
import { WidgetBaseProperties } from "../widget-base.js";
import { ActionSchema, DataSourceSchema, IconSchema } from "../common.js";
import { ajv } from "../ajv.js";

/**
 * FileTreeNode is recursive. JSON Schema's `$ref` self-references work at
 * runtime via Ajv, but `FromSchema` does not infer recursive types — so we
 * declare the TS shape by hand and use it where needed.
 */
export interface FileTreeNode {
  id: string;
  name: string;
  type: "file" | "folder";
  size?: number;
  children?: FileTreeNode[];
}

export const FileTreeNodeSchema = {
  $id: "FileTreeNode",
  type: "object",
  properties: {
    id: { type: "string", minLength: 1 },
    name: { type: "string", minLength: 1 },
    type: { enum: ["file", "folder"] },
    size: { type: "number", minimum: 0 },
    children: { type: "array", items: { $ref: "FileTreeNode" } },
  },
  required: ["id", "name", "type"],
  additionalProperties: false,
} as const;

// Register the recursive node schema with the shared Ajv instance so any
// widget that references "FileTreeNode" via $ref can compile.
if (!ajv.getSchema("FileTreeNode")) {
  ajv.addSchema(FileTreeNodeSchema);
}

export const FileTreeActionSchema = {
  type: "object",
  properties: {
    name: { type: "string", minLength: 1 },
    action: ActionSchema,
    icon: IconSchema,
  },
  required: ["name", "action"],
  additionalProperties: false,
} as const;

export const FileTreeWidgetSchema = {
  type: "object",
  properties: {
    ...WidgetBaseProperties,
    type: { const: "file-tree" },
    data_source: DataSourceSchema,
    nodes: { type: "array", items: { $ref: "FileTreeNode" } },
    on_select: ActionSchema,
    file_actions: { type: "array", items: FileTreeActionSchema },
    empty_text: { type: "string" },
  },
  required: ["name", "type", "size"],
  additionalProperties: false,
} as const;

export type FileTreeAction = FromSchema<typeof FileTreeActionSchema>;
// FileTreeWidget excludes the recursive `nodes` field from FromSchema (it
// can't see through $ref). Add it back manually.
type FileTreeWidgetBase = FromSchema<typeof FileTreeWidgetSchema>;
export type FileTreeWidget = Omit<FileTreeWidgetBase, "nodes"> & {
  nodes?: FileTreeNode[];
};
