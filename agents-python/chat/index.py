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
"""

from typing import Annotated, Any, AsyncGenerator
import asyncio
import json
import time
from datetime import datetime, timezone

from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner, function_tool

# 私有模块：不映射为路由
from ._model import llm_model
from ._logger import create_logger
from ._session import EdgeOneSession


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


# ========== SSE Helper ==========
def sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ========== 核心 handler ==========
async def handler(context: Any) -> AsyncGenerator[str, None]:
    """EdgeOne Pages Functions 入口。

    使用 OpenAI Agents SDK 的 session 参数自动处理记忆：
      - SDK 调用 session.get_items() 注入历史
      - SDK 调用 session.add_items() 写入本轮输入、助手回复和工具结果
    """
    cid = context.conversation_id   
    logger.log(f"[debug] cid: {cid}")

    body = context.request.body
    message = body.get("message") if isinstance(body, dict) else None
    if not message:
        yield sse_event("error", {"message": "'message' is required"})
        yield sse_event("done", {})
        return

    store = getattr(context, "store", None)
    if store is not None and hasattr(store, "openai_session"):
        session = store.openai_session(cid)
    elif store is not None:
        session = EdgeOneSession(store, cid)
    else:
        session = None
# 获取平台 cancel signal（asyncio.Event），当 /chat/stop 被调用时会被 set
    cancel_signal = getattr(context.request, "signal", None) or asyncio.Event()

    # 只传本轮用户输入；历史和写回都交给 OpenAI Agents SDK session 处理
    result = Runner.run_streamed(agent, input=message, session=session)
    agen = _stream_events(result).__aiter__()
    cancel_task = asyncio.ensure_future(cancel_signal.wait())
    pending: asyncio.Task | None = None

    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(agen.__anext__())

            # Race: stream event vs cancel signal vs heartbeat timeout
            done, _ = await asyncio.wait(
                {pending, cancel_task},
                timeout=HEARTBEAT_INTERVAL_S,
                return_when=asyncio.FIRST_COMPLETED,
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
                continue

            # 正常拿到一帧
            try:
                event_type, data = pending.result()
            except StopAsyncIteration:
                break
            pending = None

            yield sse_event(event_type, data)

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
