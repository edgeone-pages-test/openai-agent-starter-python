/**
 * History handler — EdgeOne Pages Functions
 * =========================================
 *
 * File path agents/history/index.ts maps to **POST /history**
 *
 * Reads conversation history from ctx.store for the given
 * pages-agent-conversation-id and returns it to the frontend
 * for restoring the chat window after a page refresh.
 *
 * Two-pass filtering (mirrors the Python agents/history/index.py):
 *   A. Filter out SDK session intermediate items (function_call,
 *      function_call_output, reasoning, etc.) — only keep "message" items.
 *   B. Group by run_id, keeping only the first user message and the last
 *      assistant message per run, so one round-trip = one Q&A pair.
 */

interface MemoryMessage {
  messageId: string;
  role?: string;
  content?: unknown;
  createdAt?: number;
  metadata?: Record<string, unknown>;
}

interface FrontendMessage {
  id: string;
  role: string;
  content: string;
  timestamp: number;
}

// ── Content extraction ──────────────────────────────────────

function contentToText(content: unknown): string {
  if (typeof content === 'string') return content;

  if (content !== null && typeof content === 'object' && !Array.isArray(content)) {
    const obj = content as Record<string, unknown>;
    if ('content' in obj) return contentToText(obj.content);
    if ('output' in obj) return contentToText(obj.output);
    if ('text' in obj) return String(obj.text ?? '');
    return '';
  }

  if (Array.isArray(content)) {
    return content
      .filter((item): item is Record<string, unknown> =>
        item !== null && typeof item === 'object',
      )
      .map(item => String(item.text ?? item.output_text ?? ''))
      .filter(Boolean)
      .join('\n');
  }

  return String(content);
}

// ── Handler ─────────────────────────────────────────────────

export async function onRequest(context: any) {
  const conversationId: string = context.conversation_id ?? '';
  const store = context.store ?? null;

  if (!store || !conversationId) {
    return new Response(JSON.stringify({ messages: [] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json; charset=UTF-8' },
    });
  }

  const history: MemoryMessage[] = await store.getMessages({
    conversationId,
    limit: 100,
    order: 'asc',
  });

  // Single-pass: filter SDK intermediate items + group by run_id
  const messages: FrontendMessage[] = [];
  const groups = new Map<string, { user: FrontendMessage | null; assistant: FrontendMessage | null; order: number }>();

  for (const item of history) {
    const role = item.role;
    if (role !== 'user' && role !== 'assistant') continue;

    const meta = item.metadata ?? {};
    if (meta.agent_sdk_session) {
      const itemType = meta.item_type as string | null | undefined;
      if (itemType != null && itemType !== 'message') continue;
    }

    const content = contentToText(item.content);
    if (!content) continue;

    const msg: FrontendMessage = {
      id: item.messageId ?? `${role}-${item.createdAt ?? 0}`,
      role: role!,
      content,
      timestamp: item.createdAt ?? 0,
    };

    const runId = meta.run_id as string | undefined;
    if (!runId) {
      messages.push(msg);
      continue;
    }

    if (!groups.has(runId)) {
      groups.set(runId, { user: null, assistant: null, order: groups.size });
    }

    const group = groups.get(runId)!;
    if (role === 'user' && group.user === null) {
      group.user = msg;
    } else if (role === 'assistant') {
      group.assistant = msg;
    }
  }

  const sorted = [...groups.values()].sort((a, b) => a.order - b.order);
  for (const group of sorted) {
    if (group.user) messages.push(group.user);
    if (group.assistant) messages.push(group.assistant);
  }

  return new Response(
    JSON.stringify({ conversation_id: conversationId, messages }),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json; charset=UTF-8' },
    },
  );
}
