# OpenAI Agents Starter (Python)

A full-stack EdgeOne Pages Agent template powered by the OpenAI Agents SDK (Python). Demonstrates how to build a streaming chat Agent with custom tools, session memory via `context.store`, and real-time tool indicators.

## Features

- **SSE Streaming Chat** — Token-by-token `text_delta` push; `tool_called` events when tools are invoked
- **Session Memory** — Persists multi-turn conversation context via EdgeOne `context.store.openai_session()`
- **Custom Agent Tools** — get_weather, get_clothing_advice, translate_text, text_statistics
- **Stop Generation** — Truly interrupts the LLM call via platform runtime cancel signal
- **Tool Indicators** — 4 animated lamps light up in real time when the Agent calls a tool

## Directory Structure

```text
openAI-agent-starter-python/
├── agents/                        # Python backend (EdgeOne Pages Functions)
│   ├── chat/
│   │   ├── index.py              # POST /chat — SSE streaming chat
│   │   └── stop.py              # POST /chat/stop — abort active run
│   ├── history/
│   │   └── index.py              # POST /history — conversation history
│   ├── _model.py                 # LLM model config (private module)
│   ├── _logger.py                # Logger utility (private module)
│   └── _tools.py                 # Agent tool definitions (private module)
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

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AI_GATEWAY_API_KEY` | Yes | LLM API key |
| `AI_GATEWAY_BASE_URL` | Yes | LLM API base URL (OpenAI-compatible) |
| `AI_GATEWAY_MODEL` | No | Model name (default: `@Pages/hy3-preview`) |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | SSE streaming chat. Header: `pages-agent-conversation-id` |
| `/chat/stop` | POST | Abort the active agent run. Body: `{ "conversation_id": "..." }` |
| `/history` | POST | Get conversation history. Header: `pages-agent-conversation-id` |

### SSE Events

```
event: text_delta     data: {"delta":"Hello"}
event: tool_called    data: {"tool":"get_weather"}
event: ping           data: {"ts":1710000000000}
event: error          data: {"message":"..."}
event: done           data: {"stopped":false}
```

## Architecture

### Backend (`agents/`)

1. **`llm_model`** — `AsyncOpenAI` + `OpenAIChatCompletionsModel` configured from environment variables
2. **`@function_tool`** — Defines custom Agent tools (weather, clothing, translate, statistics)
3. **`context.store.openai_session(cid)`** — Provides session persistence for multi-turn memory
4. **`Runner.run_streamed(agent, input, session)`** — Launches the Agent with streaming output
5. **SSE output** — Yields `text_delta`, `tool_called`, `done`, `error` events

### Frontend (`src/`)

- `App.tsx` — Orchestrates chat panel + code viewer, manages SSE stream
- `api.ts` — SSE parsing, dispatches `onTextDelta`, `onToolCalled`, `onDone`, `onError`
- `components/CodeViewer.tsx` — Static code display panel (amber CRT aesthetic) showing the agent flow
- `components/ToolIndicators.tsx` — Animated tool lamps that flash when tools are called

## Local Development

```bash
# Install frontend dependencies
npm install

# Start EdgeOne local dev (frontend + backend)
edgeone pages dev
```
