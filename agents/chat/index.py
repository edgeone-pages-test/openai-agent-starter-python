"""
Agent handler — EdgeOne Pages Functions
========================================

文件路径 agents/chat/index.py 自动映射到  **POST /chat**
（EdgeOne Pages Functions 的路由约定：目录名即路由名，index 为默认入口）

同目录下以 _ 开头的文件（如 _model.py）是私有模块，不会被映射为公开路由，
可以被 index.py import 使用。

context 约定：
    context.request.body    — dict，请求体
    context.conversation_id — 会话 ID
    context.run_id          — 本次运行 ID
    context.store           — EdgeOne 内置 store，提供 openai_session() 等方法
"""

from typing import Annotated, Any, AsyncGenerator
import asyncio
import json
import os
import time
import traceback
from urllib.parse import urlparse

from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner, function_tool

# 私有模块：不映射为路由
from ._model import llm_model
from ._logger import create_logger


# ========== Config ==========
HEARTBEAT_INTERVAL_S = 15  # 心跳间隔（秒），防止网关/CDN 因空闲超时断开连接

logger = create_logger("chat")


# ========== Tool 1: 获取天气 ==========
@function_tool
def get_weather(city: Annotated[str, "The city to get weather for"]) -> str:
    """Get the current weather for a specified city."""
    print("[debug] get_weather called")
    return f"{city}: 晴天, 18-25°C, 微风"


# ========== Tool 2: 获取穿衣建议 ==========
@function_tool
def get_clothing_advice(weather: Annotated[str, "The weather description"]) -> str:
    """Give clothing advice based on weather conditions."""
    print("[debug] get_clothing_advice called")
    return "建议穿轻薄长袖外套，搭配休闲裤和运动鞋，适合外出活动。"


# ========== Tool 3: 翻译文本 ==========
@function_tool
def translate_text(
    text: Annotated[str, "The text to translate"],
    target_language: Annotated[str, "Target language code, e.g. en, ja, fr"],
) -> str:
    """Translate text to the specified language."""
    print("[debug] translate_text called")
    translations = {
        "en": "Hello, welcome to Beijing!",
        "ja": "こんにちは、北京へようこそ！",
        "fr": "Bonjour, bienvenue à Pékin!",
    }
    return translations.get(target_language, f"[Translated to {target_language}]: {text}")


# ========== Tool 4: 统计文本信息 ==========
@function_tool
def text_statistics(text: Annotated[str, "The text to analyze"]) -> str:
    """Analyze text and return statistics like character count and word count."""
    print("[debug] text_statistics called")
    char_count = len(text)
    word_count = len(text.split())
    return f"字符数: {char_count}, 词数: {word_count}"


# ========== Agent ==========
agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant. Use the available tools to answer questions.",
    tools=[get_weather, get_clothing_advice, translate_text, text_statistics],
    model=llm_model,
)


# ========== Debug Helpers ==========
def _safe_gateway_debug() -> dict:
    """Return non-sensitive model gateway debug info."""
    base_url = os.getenv("AI_GATEWAY_BASE_URL") or ""
    parsed = urlparse(base_url)
    return {
        "api_key_set": bool(os.getenv("AI_GATEWAY_API_KEY")),
        "base_url_set": bool(base_url),
        "base_url_scheme": parsed.scheme or None,
        "base_url_host": parsed.hostname or None,
        "base_url_path": parsed.path or "/",
        "model": os.getenv("AI_GATEWAY_MODEL") or "@Pages/hy3-preview",
        "tracing_disabled": os.getenv("OPENAI_AGENTS_DISABLE_TRACING"),
    }


def _log_exception(stage: str, exc: BaseException) -> None:
    logger.error(f"[debug][exception] stage={stage} type={type(exc).__name__} message={str(exc)!r}")
    cause = getattr(exc, "__cause__", None)
    depth = 0
    while cause is not None and depth < 5:
        logger.error(
            f"[debug][exception_cause:{depth}] type={type(cause).__name__} message={str(cause)!r}"
        )
        cause = getattr(cause, "__cause__", None)
        depth += 1
    logger.error("[debug][traceback]\n" + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


# ========== SSE Helper ==========
def sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    logger.log(f"[debug][sse_event] event={event} keys={list(data.keys())}")
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ========== 核心 handler ==========
async def handler(context: Any) -> AsyncGenerator[str, None]:
    """EdgeOne Pages Functions 入口。

    使用 OpenAI Agents SDK 的 session 参数自动处理记忆：
      - SDK 调用 session.get_items() 注入历史
      - SDK 调用 session.add_items() 写入本轮输入、助手回复和工具结果
    """
    started_at = time.time()
    cid = getattr(context, "conversation_id", None)
    run_id = getattr(context, "run_id", None)
    request = getattr(context, "request", None)
    logger.log(f"[debug][handler:start] cid={cid} run_id={run_id}")
    logger.log(f"[debug][env] {_safe_gateway_debug()}")

    try:
        body = getattr(request, "body", None)
        logger.log(f"[debug][request] body_type={type(body).__name__}")
        message = body.get("message") if isinstance(body, dict) else None
        logger.log(
            f"[debug][request] message_present={bool(message)} "
            f"message_type={type(message).__name__ if message is not None else None} "
            f"message_len={len(message) if isinstance(message, str) else None}"
        )
        if not message:
            logger.log("[debug][handler] missing message; returning validation error")
            yield sse_event("error", {"message": "'message' is required"})
            yield sse_event("done", {})
            return

        store = getattr(context, "store", None)
        logger.log(
            f"[debug][session] store_present={store is not None} "
            f"store_type={type(store).__name__ if store is not None else None}"
        )
        session = store.openai_session(cid) if store is not None else None
        logger.log(f"[debug][session] session_type={type(session).__name__ if session is not None else None}")

        # 获取平台 cancel signal（asyncio.Event），当 /chat/stop 被调用时会被 set
        cancel_signal = getattr(request, "signal", None) or asyncio.Event()
        logger.log(f"[debug][cancel] signal_type={type(cancel_signal).__name__}")

        # 只传本轮用户输入；历史和写回都交给 OpenAI Agents SDK session 处理
        logger.log("[debug][runner] calling Runner.run_streamed")
        result = Runner.run_streamed(agent, input=message, session=session)
        logger.log(f"[debug][runner] result_type={type(result).__name__}")
        agen = _stream_events(result).__aiter__()
        logger.log(f"[debug][stream] async_iterator_type={type(agen).__name__}")
        cancel_task = asyncio.ensure_future(cancel_signal.wait())
        pending: asyncio.Task | None = None
        chunks_sent = 0
    except Exception as e:
        _log_exception("handler_setup", e)
        raise

    try:
        logger.log("[debug][stream_loop] entering loop")
        while True:
            if pending is None:
                logger.log(f"[debug][stream_loop] scheduling next chunk; chunks_sent={chunks_sent}")
                pending = asyncio.ensure_future(agen.__anext__())

            # Race: stream event vs cancel signal vs heartbeat timeout
            logger.log("[debug][stream_loop] waiting for stream/cancel/heartbeat")
            done, _ = await asyncio.wait(
                {pending, cancel_task},
                timeout=HEARTBEAT_INTERVAL_S,
                return_when=asyncio.FIRST_COMPLETED,
            )
            logger.log(
                f"[debug][stream_loop] wait_done={bool(done)} "
                f"pending_done={pending.done() if pending is not None else None} "
                f"cancel_done={cancel_task.done()} chunks_sent={chunks_sent}"
            )

            # Cancel signal 触发 → 立即中断
            if cancel_task in done:
                logger.log("[stream] cancel signal received; aborting stream")
                break

            # 超时 → 发送心跳保活
            if not done:
                ts = int(time.time() * 1000)
                logger.log(f"[heartbeat] ping {ts}")
                yield sse_event("ping", {"ts": ts})
                chunks_sent += 1
                continue

            # 正常拿到一帧
            try:
                event_type, data = pending.result()
            except StopAsyncIteration:
                logger.log(f"[debug][stream_loop] stream exhausted; chunks_sent={chunks_sent}")
                break
            except Exception as e:
                _log_exception("stream_next_chunk", e)
                raise
            pending = None

            logger.log(f"[debug][stream_loop] yielding event={event_type}; chunks_sent_before={chunks_sent}")
            yield sse_event(event_type, data)
            chunks_sent += 1

    except Exception as e:
        logger.error(
            f"[debug][handler:error] failed after {time.time() - started_at:.3f}s "
            f"chunks_sent={chunks_sent}"
        )
        _log_exception("handler_stream_loop", e)
        raise
    finally:
        # 清理 pending task：必须先 settle 再 aclose，否则
        # "asynchronous generator is already running" 异常
        if pending is not None and not pending.done():
            pending.cancel()
            try:
                await pending
            except BaseException:
                pass
        if not cancel_task.done():
            cancel_task.cancel()
            try:
                await cancel_task
            except BaseException:
                pass
        # 关闭 async generator → 传播 GeneratorExit 到
        # Runner.run_streamed 的内部 stream → httpx 连接，
        # 真正释放上游 LLM 请求（等同于 AbortSignal）
        try:
            await agen.aclose()
        except Exception as e:
            logger.error("agen.aclose error:", str(e))

    yield sse_event("done", {"stopped": cancel_signal.is_set()})


async def _stream_events(result) -> AsyncGenerator[tuple[str, dict], None]:
    """将 Runner stream events 转换为 SSE 帧的 async generator。

    返回 (event_type, data) 元组，主循环负责格式化和发送。
    这样可以更干净地收集文本内容用于记忆化。
    """
    async for event in result.stream_events():
        # 原始 token 增量 → 逐字推送
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            logger.log(f"[stream] text_delta: {repr(event.data.delta)}")
            yield ("text_delta", {"delta": event.data.delta})

        # 高级语义事件 → tool 调用推送
        elif event.type == "run_item_stream_event":
            if event.name == "tool_called":
                tool_name = (
                    getattr(event.item, "name", None)
                    or getattr(getattr(event.item, "raw_item", None), "name", None)
                )
                if tool_name:
                    logger.log(f"[stream] tool_called: {tool_name}")
                    yield ("tool_called", {"tool": tool_name})


# ========== 本地调试 ==========
if __name__ == "__main__":
    import asyncio
    import sys

    async def _main():
        message = sys.argv[1] if len(sys.argv) > 1 else "北京明天天气怎么样，该穿什么？"
        async for chunk in handler({"message": message}):
            print(chunk, end="", flush=True)

    asyncio.run(_main())
