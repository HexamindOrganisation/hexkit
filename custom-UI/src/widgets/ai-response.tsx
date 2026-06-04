import { useEffect, useRef, useState } from "react";
import type { WidgetProps } from "../registry/types.js";
import type { AiResponseWidget } from "../schema/widgets/ai-response.js";
import {
  useAgentUIContext,
  useConversation,
  type ConversationMessage,
} from "../runtime/context.js";
import type { AgentEvent } from "../runtime/agentBridge.js";
import { renderMarkdown } from "../lib/markdown.js";

interface PartialMessage {
  id: string;
  content: string;
}

const ACCENT = "var(--accent-color, hsl(var(--primary)))";

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
    <div ref={scrollRef} className="flex h-full min-h-0 flex-col gap-6 overflow-auto pr-1">
      <GooFilter />
      {log.map((m) => (
        <Turn key={m.id} role={m.role} content={m.content} />
      ))}
      {partials.map((p) => (
        <Turn key={p.id} role="assistant" content={p.content} streaming />
      ))}
      {status === "thinking" && partials.length === 0 && (
        <Thinking
          mode={props.thinking_indicator ?? "dots"}
          text={props.thinking_text ?? "Thinking"}
        />
      )}
    </div>
  );
}

/**
 * One conversation turn. User turns are a right-aligned bordered card (`.ucard`);
 * assistant turns are an agent-color avatar + accent tick, then prose on the
 * canvas (no bubble), with a blinking block caret while streaming.
 */
function Turn({
  role,
  content,
  streaming,
}: {
  role: ConversationMessage["role"];
  content: string;
  streaming?: boolean;
}): JSX.Element {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] whitespace-pre-wrap break-words rounded-[var(--radius)] border border-border bg-card px-4 py-2.5 text-[15px] leading-relaxed">
          {content}
        </div>
      </div>
    );
  }
  if (role === "system") {
    return (
      <div className="flex justify-center">
        <div className="rounded-md bg-muted px-3 py-1 text-xs italic text-muted-foreground">
          {content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-3.5">
      <span
        aria-hidden
        className="hx-chat-avatar mt-0.5 flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-[8px] text-[12px] font-semibold text-white"
        style={{ background: ACCENT }}
      />
      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex items-center gap-2.5">
          <span
            aria-hidden
            className="h-[2px] w-5 rounded-sm"
            style={{ background: ACCENT }}
          />
        </div>
        <div className="prose prose-sm max-w-none break-words text-[15px] leading-[1.68] text-foreground">
          {renderMarkdown(content)}
          {streaming && <span className="hx-caret" aria-hidden />}
        </div>
      </div>
    </div>
  );
}

/** Thinking: avatar pulse + shimmering status + the liquid metaball loader. */
function Thinking({
  mode,
  text,
}: {
  mode: "dots" | "text" | "none";
  text: string;
}): JSX.Element | null {
  if (mode === "none") return null;
  if (mode === "text") {
    return <div className="hx-shimmer text-[13px] font-medium">{text}…</div>;
  }
  return (
    <div className="flex gap-3.5">
      <span
        aria-hidden
        className="hx-chat-avatar mt-0.5 flex h-[30px] w-[30px] shrink-0 animate-pulse items-center justify-center rounded-[8px] text-[12px] font-semibold text-white"
        style={{ background: ACCENT }}
      />
      <div className="flex flex-col gap-2">
        <span className="hx-shimmer text-[13px] font-medium">{text}…</span>
        <div className="hx-goo" role="status" aria-label={text}>
          <span className="d1" />
          <span className="d2" />
          <span className="d3" />
        </div>
      </div>
    </div>
  );
}

/** The SVG goo filter that gels the three metaball dots together. */
function GooFilter(): JSX.Element {
  return (
    <svg width="0" height="0" aria-hidden focusable="false" className="absolute">
      <defs>
        {/* Generous filter region — the default (-10%/120%) clips the blurred,
            scaled dots (notably at the bottom). */}
        <filter
          id="hx-goo"
          x="-50%"
          y="-50%"
          width="200%"
          height="200%"
        >
          <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="b" />
          <feColorMatrix
            in="b"
            mode="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -9"
          />
        </filter>
      </defs>
    </svg>
  );
}
