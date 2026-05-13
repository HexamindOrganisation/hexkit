import { useState } from "react";
import type { WidgetProps } from "../registry/types.js";
import type {
  FileTreeWidget,
  FileTreeNode,
  FileTreeAction,
} from "../schema/widgets/file-tree.js";
import { useWidgetData, useAgentInbox } from "../runtime/context.js";
import { Button } from "../components/ui/button.js";
import { cn } from "../lib/utils.js";
import type { ActionDispatcher } from "../runtime/dispatcher.js";

export function FileTreeWidgetComponent({
  props,
  dispatcher,
}: WidgetProps<FileTreeWidget>): JSX.Element {
  const { data, loading, error } = useWidgetData<FileTreeNode[]>(
    props.data_source,
  );
  const { lastPayload } = useAgentInbox<FileTreeNode[]>();
  const nodes = lastPayload ?? data ?? props.nodes ?? [];

  if (error) {
    return (
      <div className="p-2 text-sm text-destructive">
        Error: {error.message}
      </div>
    );
  }
  if (loading && nodes.length === 0) {
    return (
      <div className="p-2 text-sm italic text-muted-foreground">Loading…</div>
    );
  }
  if (nodes.length === 0) {
    return (
      <div className="p-2 text-sm italic text-muted-foreground">
        {props.empty_text ?? "No files"}
      </div>
    );
  }

  return (
    <ul className="m-0 list-none p-0 text-sm" role="tree">
      {nodes.map((n) => (
        <TreeNode
          key={n.id}
          node={n}
          depth={0}
          {...(props.on_select && { onSelect: props.on_select })}
          {...(props.file_actions && { fileActions: props.file_actions })}
          dispatcher={dispatcher}
        />
      ))}
    </ul>
  );
}

interface TreeNodeProps {
  node: FileTreeNode;
  depth: number;
  onSelect?: string;
  fileActions?: FileTreeAction[];
  dispatcher: ActionDispatcher;
}

function TreeNode({
  node,
  depth,
  onSelect,
  fileActions,
  dispatcher,
}: TreeNodeProps): JSX.Element {
  const [expanded, setExpanded] = useState(depth === 0);
  const isFolder = node.type === "folder";

  const handleClick = () => {
    if (isFolder) setExpanded((e) => !e);
    else if (onSelect) void dispatcher.invoke(onSelect, { file: node });
  };

  return (
    <li role="treeitem" aria-expanded={isFolder ? expanded : undefined}>
      <div
        className={cn(
          "group flex items-center gap-1.5 rounded-md py-1 pr-1 hover:bg-primary/10",
          (isFolder || onSelect) && "cursor-pointer",
        )}
        style={{ paddingLeft: `${depth * 14 + 4}px` }}
        onClick={handleClick}
      >
        {isFolder ? (
          <Chevron open={expanded} />
        ) : (
          <span className="inline-block w-[14px]" />
        )}
        {isFolder ? <FolderIcon open={expanded} /> : <FileIcon />}
        <span className="flex-1 truncate">{node.name}</span>
        {!isFolder && node.size !== undefined && (
          <span className="text-xs text-muted-foreground">
            {formatSize(node.size)}
          </span>
        )}
        {!isFolder && fileActions && fileActions.length > 0 && (
          <span
            className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100"
            onClick={(e) => e.stopPropagation()}
          >
            {fileActions.map((a) => (
              <Button
                key={a.action}
                size="sm"
                variant="ghost"
                onClick={() =>
                  void dispatcher.invoke(a.action, { file: node })
                }
              >
                {a.name}
              </Button>
            ))}
          </span>
        )}
      </div>
      {isFolder && expanded && node.children && node.children.length > 0 && (
        <ul role="group" className="m-0 list-none p-0">
          {node.children.map((c) => (
            <TreeNode
              key={c.id}
              node={c}
              depth={depth + 1}
              {...(onSelect && { onSelect })}
              {...(fileActions && { fileActions })}
              dispatcher={dispatcher}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function formatSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function Chevron({ open }: { open: boolean }): JSX.Element {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("shrink-0 transition-transform", open && "rotate-90")}
      aria-hidden="true"
    >
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

function FolderIcon({ open }: { open: boolean }): JSX.Element {
  return open ? (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="currentColor"
      className="shrink-0 text-foreground"
      aria-hidden="true"
    >
      <path d="M3 5a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v2H3V5Zm0 5h18v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9Z" />
    </svg>
  ) : (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="currentColor"
      className="shrink-0 text-foreground"
      aria-hidden="true"
    >
      <path d="M3 5a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5Z" />
    </svg>
  );
}

function FileIcon(): JSX.Element {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0"
      aria-hidden="true"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}
