"""
Agent handler — EdgeOne Pages Functions
========================================

文件路径 agents/chat/index.py 自动映射到  **POST /chat**
（EdgeOne Pages Functions 的路由约定：目录名即路由名，index 为默认入口）

context 约定：
    context.request.body    — dict，请求体
    context.request.signal  — asyncio.Event，当 /chat/stop 被调用时 set
    context.conversation_id — 会话 ID
    context.run_id          — 本次运行 ID
    context.store           — EdgeOne 内置 store，提供 openai_session() 等方法
"""

from typing import Any, AsyncGenerator
import asyncio
import json

from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner

# 私有模块：不映射为路由
from .._model import llm_model
from .._logger import create_logger
from .._tools import get_weather, get_clothing_advice, translate_text, text_statistics


logger = create_logger("chat")


# ========== Agent ==========
agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant. Use the available tools to answer questions.",
    tools=[get_weather, get_clothing_advice, translate_text, text_statistics],
    model=llm_model,
)


# ========== SSE Helper ==========
def sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ========== Event Stream Generator ==========
async def _event_stream(
    message: str,
    session=None,
    cancel_signal: asyncio.Event | None = None,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE frames from the agent stream.

    Accepts cancel_signal to enable cancellation — when set,
    the loop breaks and the SDK releases its connection.
    """
    result = Runner.run_streamed(agent, input=message, session=session)

    async for event in result.stream_events():
        # Check cancel between each event
        if cancel_signal and cancel_signal.is_set():
            break

        # Raw token delta → push per-character
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            logger.log(f"[stream] text_delta: {repr(event.data.delta)}")
            yield sse_event("text_delta", {"delta": event.data.delta})

        # Semantic event → tool called
        elif event.type == "run_item_stream_event":
            if event.name == "tool_called":
                tool_name = (
                    getattr(event.item, "name", None)
                    or getattr(getattr(event.item, "raw_item", None), "name", None)
                )
                if tool_name:
                    logger.log(f"[stream] tool_called: {tool_name}")
                    yield sse_event("tool_called", {"tool": tool_name})


# ========== Core Handler ==========
async def handler(context: Any) -> AsyncGenerator[str, None]:
    """EdgeOne Pages Functions 入口。

    Uses OpenAI Agents SDK session for automatic memory:
      - SDK calls session.get_items() to inject history
      - SDK calls session.add_items() to persist assistant replies and tool results
    """
    request = getattr(context, "request", None)
    body = getattr(request, "body", None)
    message = body.get("message") if isinstance(body, dict) else None

    if not message:
        yield sse_event("error", {"message": "'message' is required"})
        yield sse_event("done", {})
        return

    # Session for memory persistence
    cid = getattr(context, "conversation_id", None)
    store = getattr(context, "store", None)
    session = store.openai_session(cid) if store else None

    # Cancel signal (asyncio.Event), set when /chat/stop is called
    cancel_signal = getattr(request, "signal", None) or asyncio.Event()
    stopped = False

    try:
        async for frame in _event_stream(message, session, cancel_signal):
            if cancel_signal.is_set():
                stopped = True
                break
            yield frame
    except asyncio.CancelledError:
        stopped = True
        logger.log("[stream] cancelled")
    except Exception as e:
        logger.error(f"[stream] error: {type(e).__name__}: {e}")
        yield sse_event("error", {"message": str(e)})
    finally:
        yield sse_event("done", {"stopped": stopped})
