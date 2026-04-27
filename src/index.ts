// Primary mount
export { AgentUI, type AgentUIProps } from "./components/AgentUI.js";

// Runtime contracts
export type { ActionDispatcher } from "./runtime/dispatcher.js";
export { nullDispatcher } from "./runtime/dispatcher.js";
export type { AgentBridge, AgentEvent } from "./runtime/agentBridge.js";

// Widget registration
export {
  defineWidget,
  WidgetRegistry,
  builtinWidgets,
  type WidgetDefinition,
  type AnyWidgetDefinition,
  type WidgetProps,
} from "./registry/index.js";

// Widget runtime hooks
export {
  useWidgetData,
  useAgentInbox,
  useAgentUIContext,
  useConversation,
  type ConversationMessage,
} from "./runtime/context.js";

// Schema + types
export {
  ConfigSchema,
  buildConfigSchema,
  type Config,
  type Page,
  type Position,
  type Size,
  type DataSource,
  type MainMenuItem,
  BuiltinWidgetSchemas,
  type BuiltinWidgetType,
  type BuiltinWidget,
  WidgetBaseShape,
  WidgetBaseSchema,
} from "./schema/index.js";

// Compile pipeline (for snapshot tests / advanced embedding)
export {
  parseYaml,
  compilePlan,
  resolve,
  normalize,
  resolveTheme,
  type RenderPlan,
  type RenderPlanWidget,
  type ResolvedConfig,
  type ResolvedWidget,
  type ResolvedTheme,
  type ThemeTokens,
  type ParseResult,
  type SourceMap,
} from "./compile/index.js";

// Diagnostics
export type {
  Diagnostic,
  DiagnosticSeverity,
  Result,
} from "./diagnostics/types.js";
