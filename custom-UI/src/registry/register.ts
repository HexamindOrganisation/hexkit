import type {
  AnyWidgetDefinition,
  WidgetDefinition,
  WidgetProps,
} from "./types.js";
import type { ComponentType } from "react";
import { compileSchema } from "../schema/ajv.js";

/**
 * Register a widget. The schema must be a JSON Schema object (preferably
 * declared with `as const` so its TS shape can be derived via
 * `FromSchema<typeof schema>` from `json-schema-to-ts`). The schema is
 * compiled with the shared Ajv instance at definition time.
 */
export function defineWidget<TProps>(
  spec: WidgetDefinition<TProps>,
): AnyWidgetDefinition {
  const validate = compileSchema(spec.schema);
  return {
    type: spec.type,
    schema: spec.schema,
    validate,
    component: spec.component as ComponentType<WidgetProps<unknown>>,
    ...(spec.defaults && { defaults: spec.defaults as Record<string, unknown> }),
    ...(spec.chromeless !== undefined && { chromeless: spec.chromeless }),
    ...(spec.slot && { slot: spec.slot }),
  };
}

export class WidgetRegistry {
  private readonly defs: Map<string, AnyWidgetDefinition> = new Map();

  constructor(initial: readonly AnyWidgetDefinition[] = []) {
    for (const def of initial) this.register(def);
  }

  register(def: AnyWidgetDefinition): void {
    this.defs.set(def.type, def);
  }

  registerMany(defs: readonly AnyWidgetDefinition[]): void {
    for (const d of defs) this.register(d);
  }

  get(type: string): AnyWidgetDefinition | undefined {
    return this.defs.get(type);
  }

  has(type: string): boolean {
    return this.defs.has(type);
  }

  types(): string[] {
    return Array.from(this.defs.keys());
  }

  all(): AnyWidgetDefinition[] {
    return Array.from(this.defs.values());
  }

  extend(extras: readonly AnyWidgetDefinition[]): WidgetRegistry {
    const clone = new WidgetRegistry(this.all());
    clone.registerMany(extras);
    return clone;
  }
}
