# OpenAI Agents Starter (Python)

A full-stack EdgeOne Makers Agent template powered by the OpenAI Agents SDK (Python). Demonstrates how to build a streaming chat Agent with custom tools, session memory via `context.store`, and real-time tool indicators.

## Deploy

[![Deploy with EdgeOne Pages](https://cdnstatic.tencentcs.com/edgeone/pages/deploy.svg)](https://edgeone.ai/makers/new?template=openai-agents-starter-python&from=within&fromAgent=1&agentLang=python)

## Features

- **SSE Streaming Chat** — Token-by-token `text_delta` push; `tool_called` events when tools are invoked
- **Session Memory** — Persists multi-turn conversation context via EdgeOne `context.store.openai_session()`
- **Custom Agent Tools** — get_weather, get_clothing_advice, translate_text, text_statistics
- **Stop Generation** — Truly interrupts the LLM call via platform runtime cancel signal
- **Tool Indicators** — 4 animated lamps light up in real time when the Agent calls a tool

## Directory Structure

```text
openAI-agent-starter-python/
├── agents/                        # Stateful EdgeOne Makers Agent Functions (Python)
│   ├── chat/
│   │   ├── index.py              # POST /chat — SSE streaming chat
│   │   └── stop.py               # POST /chat/stop — abort active run
│   ├── _logger.py                # Logger utility (private module)
│   └── _tools.py                 # Agent tool definitions (private module)
├── cloud-functions/               # Stateless EdgeOne Pages Python cloud functions
│   ├── history/
│   │   └── index.py              # POST /history — load conversation messages
│   └── _logger.py                # Logger utility
├── src/                           # React frontend (Vite + TypeScript)
│   ├── App.tsx                    # Main app component
│   ├── api.ts                    # Backend API wrappers (SSE streaming)
│   ├── types.ts                  # Type definitions
│   └── components/               # UI components
│       ├── ChatWindow.tsx        # Chat window
│       ├── ChatBubble.tsx        # Message bubble (Markdown support)
│       ├── ChatInput.tsx         # Input box + presets + stop button
│       ├── CodeViewer.tsx        # Code display panel (CRT aesthetic)
│       ├── ToolIndicators.tsx    # Tool indicator container
│       └── ToolLamp.tsx          # Single tool indicator lamp
├── index.html                    # Entry HTML
├── package.json                  # Frontend dependencies
├── requirements.txt              # Python dependencies
├── vite.config.ts                # Vite config
├── tsconfig.json                 # TypeScript config
└── .gitignore                    # Git ignore rules
```

> Files prefixed with `_` are private modules — not mapped as public routes by EdgeOne.
>
> **Why two backend folders?** `agents/` holds long-running, stateful routes (active SSE streams, per-conversation abort signals); `cloud-functions/` holds short, stateless routes that just read `context.agent.store`. Splitting them keeps history requests from contending with an active chat for the per-conversation lock.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AI_GATEWAY_API_KEY` | Yes | LLM API key |
| `AI_GATEWAY_BASE_URL` | Yes | LLM API base URL (OpenAI-compatible) |
| `AI_GATEWAY_MODEL` | No | Model name (default: `@makers/hy3-preview`) |

## API Endpoints

| Endpoint | Method | Side | Description |
|----------|--------|------|-------------|
| `/chat` | POST | `agents/` | SSE streaming chat. Header: `makers-conversation-id` |
| `/chat/stop` | POST | `agents/` | Abort the active agent run. Body: `{ "conversation_id": "..." }` |
| `/history` | POST | `cloud-functions/` | Get conversation history. Body: `{ "conversation_id": "..." }` |

### SSE Events

```
event: text_delta     data: {"delta":"Hello"}
event: tool_called    data: {"tool":"get_weather"}
event: ping           data: {"ts":1710000000000}
event: error          data: {"message":"..."}
event: done           data: {"stopped":false}
```

## Architecture

### Backend (`agents/` + `cloud-functions/`)

`agents/` is where the stateful work happens — it owns the live SSE stream and the AbortSignal for the running model call:

1. **`agents/chat/index.py`** — Configures `AsyncOpenAI` + `OpenAIChatCompletionsModel` from environment variables and streams the Agent response
2. **`@function_tool`** — Defines custom Agent tools (weather, clothing, translate, statistics)
3. **`context.store.openai_session(cid)`** — Provides session persistence for multi-turn memory
4. **`Runner.run_streamed(agent, input, session)`** — Launches the Agent with streaming output
5. **SSE output** — Yields `text_delta`, `tool_called`, `done`, `error` events

`cloud-functions/history` is the stateless `/history` route — it just reads `context.agent.store.get_messages()` to restore the chat after a page refresh, without spinning up an agent run.

### Frontend (`src/`)

- `App.tsx` — Orchestrates chat panel + code viewer, manages SSE stream
- `api.ts` — SSE parsing, dispatches `onTextDelta`, `onToolCalled`, `onDone`, `onError`
- `components/CodeViewer.tsx` — Static code display panel (amber CRT aesthetic) showing the agent flow
- `components/ToolIndicators.tsx` — Animated tool lamps that flash when tools are called

## Local Development

```bash
# Install frontend dependencies
npm install

# Install backend Python dependencies
pip install -r requirements.txt

# Start EdgeOne local dev (frontend + backend)
edgeone makers dev
```
