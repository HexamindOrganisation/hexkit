import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { ActionDispatcher } from "./dispatcher.js";
import type { AgentBridge, AgentEvent } from "./agentBridge.js";
import type { DataSource } from "../schema/common.js";
import type { Diagnostic } from "../diagnostics/types.js";

interface InboxState {
  history: unknown[];
  lastPayload: unknown;
  version: number;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

interface AgentUIContextValue {
  dispatcher: ActionDispatcher;
  agent?: AgentBridge;
  /** Per-widget tool-call inbox state, keyed by widget name. */
  inboxes: Map<string, InboxState>;
  /** Subscribe to inbox changes for a given widget name. */
  subscribeInbox: (name: string, cb: () => void) => () => void;
  /** Subscribe to container-targeted events (token/message/status). */
  subscribeContainer: (cb: (event: AgentEvent) => void) => () => void;
  pushDiagnostic: (d: Diagnostic) => void;
  diagnostics: Diagnostic[];
  /** Full conversation log (user + assistant + system, finalized only). */
  conversation: ConversationMessage[];
  /** Id of the conversation currently loaded into the log, if any. */
  selectedConversationId?: string;
  /** Append a user message to the conversation log. */
  pushUserMessage: (content: string) => void;
  /**
   * Replace the conversation log with a previously-saved conversation.
   * Subsequent user submits and assistant replies append to the loaded log.
   */
  loadConversation: (id: string, messages: ConversationMessage[]) => void;
  /** Clear the conversation log and deselect any loaded conversation. */
  startNewConversation: () => void;
}

const AgentUIContext = createContext<AgentUIContextValue | null>(null);

export interface AgentUIProviderProps {
  dispatcher: ActionDispatcher;
  agent?: AgentBridge;
  /** Widget names known to the render plan; used to warn on stray tool-calls. */
  knownWidgetNames: readonly string[];
  /**
   * Seed the conversation log with previously-saved messages (e.g. when the
   * host loads an existing conversation). Used as the initial state; the
   * provider remounts per conversation, so this is sufficient — live submits
   * and replies append to it.
   */
  initialMessages?: ConversationMessage[];
  onEvent?: (event: AgentEvent) => void;
  onDiagnostic?: (d: Diagnostic) => void;
  children: ReactNode;
}

export function AgentUIProvider({
  dispatcher,
  agent,
  knownWidgetNames,
  initialMessages,
  onEvent,
  onDiagnostic,
  children,
}: AgentUIProviderProps): JSX.Element {
  const inboxesRef = useRef<Map<string, InboxState>>(new Map());
  const inboxSubsRef = useRef<Map<string, Set<() => void>>>(new Map());
  const containerSubsRef = useRef<Set<(e: AgentEvent) => void>>(new Set());
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const [conversation, setConversation] = useState<ConversationMessage[]>(
    initialMessages ?? [],
  );
  const [selectedConversationId, setSelectedConversationId] = useState<
    string | undefined
  >(undefined);

  const pushUserMessage = useCallback((content: string) => {
    setConversation((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}-${prev.length}`,
        role: "user",
        content,
        timestamp: Date.now(),
      },
    ]);
  }, []);

  const loadConversation = useCallback(
    (id: string, messages: ConversationMessage[]) => {
      setSelectedConversationId(id);
      setConversation(messages);
    },
    [],
  );

  const startNewConversation = useCallback(() => {
    setSelectedConversationId(undefined);
    setConversation([]);
  }, []);
  const knownSet = useMemo(
    () => new Set(knownWidgetNames),
    [knownWidgetNames],
  );

  const pushDiagnostic = (d: Diagnostic) => {
    setDiagnostics((prev) => [...prev, d]);
    onDiagnostic?.(d);
  };

  const subscribeInbox = (name: string, cb: () => void) => {
    let set = inboxSubsRef.current.get(name);
    if (!set) {
      set = new Set();
      inboxSubsRef.current.set(name, set);
    }
    set.add(cb);
    return () => {
      set!.delete(cb);
    };
  };

  const subscribeContainer = (cb: (event: AgentEvent) => void) => {
    containerSubsRef.current.add(cb);
    return () => {
      containerSubsRef.current.delete(cb);
    };
  };

  useEffect(() => {
    if (!agent) return;
    const unsub = agent.subscribeAgentOutput((event) => {
      onEvent?.(event);
      if (event.kind === "tool-call") {
        // Name-only, strict. Reject events without a widget target or with
        // no matching widget — no broadcast, no fallback.
        if (!event.widget) {
          pushDiagnostic({
            severity: "warning",
            code: "agent.tool-call-no-widget",
            message: "tool-call event missing required `widget` field; dropped",
            path: [],
          });
          return;
        }
        if (!knownSet.has(event.widget)) {
          pushDiagnostic({
            severity: "warning",
            code: "agent.tool-call-unknown-widget",
            message: `tool-call targets unknown widget "${event.widget}"; dropped`,
            path: [],
          });
          return;
        }
        const prev = inboxesRef.current.get(event.widget) ?? {
          history: [],
          lastPayload: undefined,
          version: 0,
        };
        const next: InboxState = {
          history: [...prev.history, event.payload],
          lastPayload: event.payload,
          version: prev.version + 1,
        };
        inboxesRef.current.set(event.widget, next);
        inboxSubsRef.current.get(event.widget)?.forEach((cb) => cb());
        return;
      }
      // Container-bound events.
      containerSubsRef.current.forEach((cb) => cb(event));
      if (event.kind === "message") {
        setConversation((prev) => [
          ...prev,
          {
            id: event.messageId ?? `assistant-${Date.now()}-${prev.length}`,
            role: event.role,
            content: event.content,
            timestamp: Date.now(),
          },
        ]);
      } else if (event.kind === "error") {
        pushDiagnostic({
          severity: "error",
          code: "agent.error",
          message: event.message,
          path: [],
        });
        setConversation((prev) => [
          ...prev,
          {
            id: `error-${Date.now()}-${prev.length}`,
            role: "system",
            content: `Error: ${event.message}`,
            timestamp: Date.now(),
          },
        ]);
      }
    });
    return unsub;
  }, [agent, knownSet, onEvent]);

  const value = useMemo<AgentUIContextValue>(
    () => ({
      dispatcher,
      ...(agent && { agent }),
      inboxes: inboxesRef.current,
      subscribeInbox,
      subscribeContainer,
      pushDiagnostic,
      diagnostics,
      conversation,
      ...(selectedConversationId !== undefined && { selectedConversationId }),
      pushUserMessage,
      loadConversation,
      startNewConversation,
    }),
    [
      dispatcher,
      agent,
      diagnostics,
      conversation,
      selectedConversationId,
      pushUserMessage,
      loadConversation,
      startNewConversation,
    ],
  );

  return (
    <AgentUIContext.Provider value={value}>{children}</AgentUIContext.Provider>
  );
}

export function useAgentUIContext(): AgentUIContextValue {
  const ctx = useContext(AgentUIContext);
  if (!ctx) throw new Error("useAgentUIContext must be used inside <AgentUI>");
  return ctx;
}

/**
 * Read the full conversation log (user + assistant + system, finalized).
 * Streaming token events are not included; emit a final `message` event to
 * land in history.
 */
export function useConversation(): { messages: ConversationMessage[] } {
  const ctx = useAgentUIContext();
  return { messages: ctx.conversation };
}

// Widget-scoped context so hooks know which widget they're inside.
const WidgetNameContext = createContext<string | null>(null);

export function WidgetScope({
  name,
  children,
}: {
  name: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <WidgetNameContext.Provider value={name}>
      {children}
    </WidgetNameContext.Provider>
  );
}

function useWidgetName(): string {
  const n = useContext(WidgetNameContext);
  if (!n) throw new Error("Widget hooks must be used inside a <WidgetHost>");
  return n;
}

/**
 * Widget data hook. Backed by `dispatcher.subscribe` when available and
 * `dataSource.subscribe` is true; otherwise calls `invoke` once.
 */
export function useWidgetData<T>(
  dataSource: DataSource | undefined,
): { data: T | undefined; loading: boolean; error?: Error; refresh: () => void } {
  const { dispatcher } = useAgentUIContext();
  const [data, setData] = useState<T | undefined>(undefined);
  const [loading, setLoading] = useState<boolean>(!!dataSource);
  const [error, setError] = useState<Error | undefined>(undefined);
  const [refreshTick, setRefreshTick] = useState(0);
  const refresh = useCallback(() => setRefreshTick((t) => t + 1), []);

  useEffect(() => {
    if (!dataSource) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(undefined);

    if (dataSource.subscribe && dispatcher.subscribe) {
      const unsub = dispatcher.subscribe(
        dataSource.action,
        dataSource.args,
        (d) => {
          if (!cancelled) {
            setData(d as T);
            setLoading(false);
          }
        },
        (e) => {
          if (!cancelled) {
            setError(e instanceof Error ? e : new Error(String(e)));
            setLoading(false);
          }
        },
      );
      return () => {
        cancelled = true;
        unsub();
      };
    }

    dispatcher
      .invoke(dataSource.action, dataSource.args)
      .then((d) => {
        if (!cancelled) {
          setData(d as T);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e : new Error(String(e)));
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [dataSource?.action, JSON.stringify(dataSource?.args), dataSource?.subscribe, dispatcher, refreshTick]);

  const out: { data: T | undefined; loading: boolean; error?: Error; refresh: () => void } = {
    data,
    loading,
    refresh,
  };
  if (error) out.error = error;
  return out;
}

/**
 * Returns the latest tool-call payload routed to the enclosing widget, along
 * with its full history. Isolation-safe: a widget can only read its own inbox.
 */
export function useAgentInbox<TPayload = unknown>(): {
  lastPayload: TPayload | undefined;
  history: TPayload[];
} {
  const name = useWidgetName();
  const { inboxes, subscribeInbox } = useAgentUIContext();
  const [, forceRender] = useState(0);

  useEffect(() => {
    const unsub = subscribeInbox(name, () => forceRender((x) => x + 1));
    return unsub;
  }, [name, subscribeInbox]);

  const state = inboxes.get(name);
  return {
    lastPayload: state?.lastPayload as TPayload | undefined,
    history: (state?.history ?? []) as TPayload[],
  };
}
