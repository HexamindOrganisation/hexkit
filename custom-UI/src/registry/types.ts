import type { ComponentType } from "react";
import type { ValidateFunction } from "ajv";
import type { ActionDispatcher } from "../runtime/dispatcher.js";

/**
 * Props passed to every widget component. `props` is the validated,
 * widget-specific subtree from the YAML.
 */
export interface WidgetProps<TProps = unknown> {
  id: string;
  name: string;
  props: TProps;
  dispatcher: ActionDispatcher;
}

/**
 * Where a widget renders inside the AgentUI shell.
 * - "main"   (default): the widget is part of the layout (grid/flex).
 *                        Honors `position` and `size.width`.
 * - "footer": rendered outside the layout, pinned to the bottom of the page.
 *             Spans the full width. `position` is ignored.
 */
export type WidgetSlot = "main" | "footer";

/**
 * A widget definition supplied to `defineWidget`. The schema is an `as const`
 * JSON Schema object; the validated props type is supplied by the caller
 * (typically via `FromSchema<typeof schema>` from `json-schema-to-ts`).
 */
export interface WidgetDefinition<TProps = unknown> {
  type: string;
  schema: object;
  component: ComponentType<WidgetProps<TProps>>;
  defaults?: Partial<TProps>;
  /** When true, WidgetHost skips the default border/padding chrome. */
  chromeless?: boolean;
  /** Default "main". "footer" widgets render outside the layout, pinned to the page bottom. */
  slot?: WidgetSlot;
}

/**
 * Erased form stored in the registry. The Ajv validator is precompiled at
 * registration time. Component is widened to `any` so definitions for
 * different schemas share a homogeneous container without TypeScript's
 * invariant component-position tripping us up.
 */
export interface AnyWidgetDefinition {
  type: string;
  schema: object;
  validate: ValidateFunction;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  component: ComponentType<WidgetProps<any>>;
  defaults?: Record<string, unknown>;
  chromeless?: boolean;
  slot?: WidgetSlot;
}
