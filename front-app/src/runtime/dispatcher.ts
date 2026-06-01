import type { ActionDispatcher } from "agent-ui";

import { invokeConversationAction } from "../api/conversations";

/**
 * Resolves widget `data_source` / action calls against the proxy. Scoped to
 * the active conversation; widget actions POST to
 * `/conversations/{id}/actions/{name}` and return `{ result, events }`.
 *
 * When there's no conversation yet (the greeting), actions resolve to
 * `undefined` rather than erroring — most widgets degrade to their empty state.
 */
export function makeDispatcher(
  getConversationId: () => string | null,
): ActionDispatcher {
  return {
    async invoke(action: string, args?: unknown): Promise<unknown> {
      const conversationId = getConversationId();
      if (!conversationId) return undefined;
      const { result } = await invokeConversationAction(
        conversationId,
        action,
        args ?? {},
      );
      return result;
    },
    has() {
      // Assume any named action is dispatchable; the backend 404s unknown ones.
      return true;
    },
  };
}
