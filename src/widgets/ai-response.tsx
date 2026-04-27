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
      <div className="flex min-h-[6rem] items-center justify-center text-sm italic text-muted-foreground">
        {props.empty_text ?? (agent ? "" : "No agent bridge connected.")}
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      className="flex max-h-[28rem] flex-col gap-3 overflow-auto"
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
        "flex w-full flex-col",
        role === "user" && "items-end pl-12",
        role === "assistant" && "items-start pr-12",
        role === "system" && "items-center",
      )}
    >
      <span
        className={cn(
          "max-w-[min(65ch,_100%)] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm leading-relaxed shadow-sm",
          role === "user" && "bg-primary text-primary-foreground rounded-br-md",
          role === "assistant" &&
            "bg-accent text-accent-foreground rounded-bl-md",
          role === "system" &&
            "bg-muted text-xs italic text-muted-foreground shadow-none",
          partial && "opacity-90",
        )}
      >
        {content}
      </span>
    </div>
  );
}
