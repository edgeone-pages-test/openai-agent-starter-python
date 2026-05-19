/**
 * Private module (file name starts with _) — not mapped as a public route.
 * Used to configure LLM model from EdgeOne runtime context.env.
 *
 * Imported by ./index.ts via `import { createLlmModel } from './_model'`
 */

import OpenAI from 'openai';
import { OpenAIChatCompletionsModel } from '@openai/agents';

type RuntimeEnv = Record<string, string | undefined>;

export function createLlmModel(env: RuntimeEnv) {
  console.log('[debug] createLlmModel called', env);
  const llmClient = new OpenAI({
    apiKey:  env.AI_GATEWAY_API_KEY,
    baseURL: env.AI_GATEWAY_BASE_URL,
  });

  // OpenAIChatCompletionsModel(client, model) — positional arguments
  return new OpenAIChatCompletionsModel(
    llmClient,
    env.AI_GATEWAY_MODEL ?? "@Pages/glm-5",
  );
}