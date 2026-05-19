/**
 * Agent handler — EdgeOne Pages Functions
 * ========================================
 *
 * File path agents/chat/index.ts maps to **POST /chat**
 * (EdgeOne Pages Functions routing convention: directory name = route, index = default entry)
 *
 * Files starting with _ (e.g. _model.ts) are private modules, not mapped as public routes.
 *
 * context convention:
 *   context.request.body    — object, request body
 *   context.request.signal  — AbortSignal, set when /chat/stop is called
 *   context.conversationId  — conversation ID
 *   context.runId           — current run ID
 */

import { run, Agent, tool, type Session } from '@openai/agents';
import { z } from 'zod';
import { createLlmModel } from '../_model';
import { createLogger } from '../_logger';

// ========== Config ==========
const HEARTBEAT_INTERVAL_MS = 15_000; // Heartbeat interval to keep connection alive

const logger = createLogger('chat');

// ========== Tool 1: Get Weather ==========
const getWeather = tool({
  name: 'get_weather',
  description: 'Get the current weather for a specified city.',
  parameters: z.object({
    city: z.string().describe('The city to get weather for'),
  }),
  execute: async ({ city }) => {
    console.log('[debug] get_weather called');
    return `${city}: 晴天, 18-25°C, 微风`;
  },
});

// ========== Tool 2: Get Clothing Advice ==========
const getClothingAdvice = tool({
  name: 'get_clothing_advice',
  description: 'Give clothing advice based on weather conditions.',
  parameters: z.object({
    weather: z.string().describe('The weather description'),
  }),
  execute: async ({ weather: _weather }) => {
    console.log('[debug] get_clothing_advice called');
    return '建议穿轻薄长袖外套，搭配休闲裤和运动鞋，适合外出活动。';
  },
});

// ========== Tool 3: Translate Text ==========
const translateText = tool({
  name: 'translate_text',
  description: 'Translate text to the specified language.',
  parameters: z.object({
    text: z.string().describe('The text to translate'),
    target_language: z.string().describe('Target language code, e.g. en, ja, fr'),
  }),
  execute: async ({ text, target_language }) => {
    console.log('[debug] translate_text called');
    const translations: Record<string, string> = {
      en: 'Hello, welcome to Beijing!',
      ja: 'こんにちは、北京へようこそ！',
      fr: 'Bonjour, bienvenue à Pékin!',
    };
    return translations[target_language] ?? `[Translated to ${target_language}]: ${text}`;
  },
});

// ========== Tool 4: Text Statistics ==========
const textStatistics = tool({
  name: 'text_statistics',
  description: 'Analyze text and return statistics like character count and word count.',
  parameters: z.object({
    text: z.string().describe('The text to analyze'),
  }),
  execute: async ({ text }) => {
    console.log('[debug] text_statistics called');
    const charCount = text.length;
    const wordCount = text.trim().split(/\s+/).filter(Boolean).length;
    return `字符数: ${charCount}, 词数: ${wordCount}`;
  },
});

// ========== Agent ==========
type RuntimeEnv = Record<string, string | undefined>;

function createAgent(env: RuntimeEnv) {
  return new Agent({
    name: 'Assistant',
    instructions: 'You are a helpful assistant. Use the available tools to answer questions.',
    tools: [getWeather, getClothingAdvice, translateText, textStatistics],
    model: createLlmModel(env),
  });
}

// ========== SSE Helper ==========
function sseFrame(event: string, data: Record<string, unknown>): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

// ========== Event Stream Generator ==========
/**
 * Async generator that yields SSE frames from the agent stream.
 * Accepts AbortSignal to enable cancellation — when aborted,
 * the for-await loop breaks naturally and the SDK releases its connection.
 *
 * The SDK session handles memory read/write automatically when provided.
 */
async function* eventStream(
  agentInstance: Agent,
  message: string,
  signal?: AbortSignal,
  session?: Session,
): AsyncGenerator<string, void> {
  const result = await run(agentInstance, message, { stream: true, signal, session });

  for await (const event of result.toStream()) {
    // Check abort between each event
    if (signal?.aborted) break;

    // Raw token delta → push per-character
    if (
      event.type === 'raw_model_stream_event' &&
      (event as any).data?.type === 'output_text_delta'
    ) {
      const delta = (event as any).data.delta as string;
      logger.log(`[stream] text_delta: ${JSON.stringify(delta)}`);
      yield sseFrame('text_delta', { delta });
    }

    // Semantic event → tool called
    if (event.type === 'run_item_stream_event' && (event as any).name === 'tool_called') {
      const toolName: string | null =
        (event as any).item?.name ??
        (event as any).item?.rawItem?.name ??
        null;
      if (toolName) {
        logger.log(`[stream] tool_called: ${toolName}`);
        yield sseFrame('tool_called', { tool: toolName });
      }
    }
  }

}

// ========== Core Handler ==========
/**
 * EdgeOne Pages Functions entry point.
 *
 * Uses the same pattern as the reference deepagents-test-starter/agents/stream.ts:
 *   - An async generator (eventStream) produces SSE frames
 *   - A ReadableStream feeds chunks to the Response
 *   - Cancel signal (from /chat/stop) breaks the for-await loop,
 *     which propagates to the SDK's internal stream and truly releases
 *     the upstream LLM connection
 */
export async function onRequest(context: any) {
  const body = context.request.body ?? {};
  const message = body.message as string | undefined;

  if (!message) {
    return new Response(
      JSON.stringify({ error: "'message' is required" }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    );
  }

  // Get platform cancel signal (AbortSignal), set when /chat/stop is called
  const signal: AbortSignal | undefined = context.request.signal;

  // Use EdgeOne CLI built-in store session adapter for persistence
  const store = context.store ?? null;
  const conversationId: string = context.conversation_id ?? '';
  const session: Session | undefined = store && conversationId
    ? store.openaiSession(conversationId)
    : undefined;

  const agent = createAgent(context.env ?? {});
  const encoder = new TextEncoder();
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  let stopped = false;

  const stream = new ReadableStream({
    async start(controller) {
      // Heartbeat: send ping periodically to keep connection alive
      heartbeatTimer = setInterval(() => {
        if (!signal?.aborted) {
          const ts = Date.now();
          logger.log(`[heartbeat] ping ${ts}`);
          controller.enqueue(encoder.encode(sseFrame('ping', { ts })));
        }
      }, HEARTBEAT_INTERVAL_MS);

      try {
        const gen = eventStream(agent, message, signal, session);
        let next = await gen.next();
        while (!next.done) {
          if (signal?.aborted) {
            stopped = true;
            break;
          }
          controller.enqueue(encoder.encode(next.value));
          next = await gen.next();
        }
      } catch (e: unknown) {
        const error = e as Error;
        if (error.name === 'AbortError' || signal?.aborted) {
          stopped = true;
          logger.log('[stream] aborted by user');
        } else {
          logger.error('[stream] error:', error.message, error.stack);
          controller.enqueue(
            encoder.encode(sseFrame('error', { message: String(error.message ?? e) })),
          );
        }
      } finally {
        if (heartbeatTimer) clearInterval(heartbeatTimer);

        // Send done frame
        controller.enqueue(encoder.encode(sseFrame('done', { stopped })));
        controller.close();
      }
    },
    cancel() {
      // Triggered when client disconnects
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      logger.log('[stream] client disconnected');
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
