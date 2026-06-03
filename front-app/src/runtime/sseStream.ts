import { getToken } from "../api/client";

import type { RuntimeEvent } from "./types.js";


/**
 * Open the platform backend's chat SSE stream and yield typed events.
 *
 * `fetch()` + `ReadableStream` because browser `EventSource` is GET-only.
 * The parser tolerates `\n` and `\r\n` (sse-starlette uses `\r\n`).
 *
 * The generator's `try/finally` releases the reader lock so an early `break`
 * (e.g. on cancel) cleanly tears the response down.
 */
export async function* streamChat(
  conversationId: string,
  content: string,
  signal?: AbortSignal,
  fileIds?: string[],
): AsyncGenerator<RuntimeEvent, void, void> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({
        content,
        ...(fileIds && fileIds.length ? { file_ids: fileIds } : {}),
      }),
      ...(signal && { signal }),
    },
  );
  if (!res.ok || !res.body) {
    throw new Error(`stream failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line. Split, parse, and keep any
      // partial trailing frame for the next chunk.
      for (;;) {
        const sepIndex = buffer.search(/\r?\n\r?\n/);
        if (sepIndex === -1) break;
        const frame = buffer.slice(0, sepIndex);
        buffer = buffer.slice(
          sepIndex + (buffer[sepIndex] === "\r" ? 4 : 2),
        );
        const parsed = parseFrame(frame);
        if (parsed) yield parsed;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function parseFrame(block: string): RuntimeEvent | null {
  let data: string | null = null;
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("data:")) {
      data = line.slice(5).trim();
    }
  }
  if (!data) return null;
  try {
    return JSON.parse(data) as RuntimeEvent;
  } catch {
    return null;
  }
}
