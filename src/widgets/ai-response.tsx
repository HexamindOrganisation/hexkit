import { useEffect, useRef, useState } from "react";
import type { WidgetProps } from "../registry/types.js";
import type { AiResponseWidget } from "../schema/widgets/ai-response.js";
import {
  useAgentUIContext,
  useConversation,
  type ConversationMessage,
} from "../runtime/context.js";
import type { AgentEvent } from "../runtime/agentBridge.js";
import { cn } from "../lib/utils.js";

interface PartialMessage {
  id: string;
  content: string;
}

export function AiResponseWidgetComponent({
  props,
}: WidgetProps<AiResponseWidget>): JSX.Element {
  const { agent, subscribeContainer } = useAgentUIContext();
  const { messages: log } = useConversation();
  const [partials, setPartials] = useState<PartialMessage[]>([]);
  const [status, setStatus] = useState<"idle" | "thinking" | "responding">(
    "idle",
  );
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!agent) return;
    const unsub = subscribeContainer((event: AgentEvent) => {
      if (event.kind === "token") {
        const id = event.messageId ?? "stream";
        setPartials((prev) => {
          const idx = prev.findIndex((p) => p.id === id);
          if (idx === -1) return [...prev, { id, content: event.text }];
          const next = [...prev];
          next[idx] = { id, content: next[idx]!.content + event.text };
          return next;
        });
      } else if (event.kind === "message") {
        // Finalized — provider has appended it to the conversation log.
        // Drop the partial (if any) so we don't double-render.
        const id = event.messageId;
        if (!id) return;
        setPartials((prev) => prev.filter((p) => p.id !== id));
      } else if (event.kind === "status") {
        setStatus(event.state);
      }
    });
    return unsub;
  }, [agent, subscribeContainer]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [log.length, partials.length, status]);

  const isEmpty =
    log.length === 0 && partials.length === 0 && status === "idle";

  if (isEmpty) {
    return (
      <div className="flex h-full items-center justify-center bg-background px-4 py-3 text-sm italic text-muted-foreground">
        {props.empty_text ?? (agent ? "" : "No agent bridge connected.")}
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      className="flex h-full flex-col gap-2 overflow-auto bg-background px-4 py-3"
    >
      {log.map((m) => (
        <Bubble key={m.id} role={m.role} content={m.content} />
      ))}
      {partials.map((p) => (
        <Bubble key={p.id} role="assistant" content={p.content} partial />
      ))}
      {status !== "idle" && (
        <div className="text-xs italic text-muted-foreground">
          {status === "thinking" ? "…thinking" : "…responding"}
        </div>
      )}
    </div>
  );
}

function Bubble({
  role,
  content,
  partial,
}: {
  role: ConversationMessage["role"];
  content: string;
  partial?: boolean;
}): JSX.Element {
  return (
    <div
      className={cn(
        "flex flex-col",
        role === "user" && "items-end",
        role === "assistant" && "items-start",
        role === "system" && "items-center",
      )}
    >
      <span
        className={cn(
          "max-w-[85%] whitespace-pre-wrap break-words rounded-md px-3 py-2 text-sm",
          role === "user" && "bg-primary text-primary-foreground",
          role === "assistant" && "bg-accent text-accent-foreground",
          role === "system" &&
            "bg-muted text-xs italic text-muted-foreground",
          partial && "opacity-90",
        )}
      >
        {content}
      </span>
    </div>
  );
}
