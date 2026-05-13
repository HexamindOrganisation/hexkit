import { useState } from "react";
import type { WidgetProps } from "../registry/types.js";
import type { AiChatInputWidget } from "../schema/widgets/ai-chat-input.js";
import { useAgentUIContext } from "../runtime/context.js";
import { Button } from "../components/ui/button.js";
import { Textarea } from "../components/ui/textarea.js";

export function AiChatInputWidgetComponent({
  props,
}: WidgetProps<AiChatInputWidget>): JSX.Element {
  const { dispatcher, agent, pushUserMessage } = useAgentUIContext();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const canFallback = !agent && (dispatcher.has?.("user-submit") ?? false);
  const inert = !agent && !canFallback;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;
    setSubmitting(true);
    try {
      pushUserMessage(t);
      if (agent) {
        await agent.onUserSubmit(t);
      } else if (canFallback) {
        await dispatcher.invoke("user-submit", { text: t });
      } else {
        // eslint-disable-next-line no-console
        console.warn(
          "[agent-ui] ai-chat-input has no AgentBridge nor a 'user-submit' dispatcher action; input is inert.",
        );
      }
      setText("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="flex items-end gap-2" onSubmit={onSubmit}>
      <Textarea
        rows={props.rows ?? 2}
        placeholder={
          inert
            ? "Input disabled — no bridge"
            : props.placeholder ?? "Ask anything…"
        }
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={inert || submitting}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void onSubmit(e as unknown as React.FormEvent);
          }
        }}
      />
      <Button
        type="submit"
        disabled={inert || submitting || !text.trim()}
      >
        {props.submit_label ?? "Send"}
      </Button>
    </form>
  );
}
