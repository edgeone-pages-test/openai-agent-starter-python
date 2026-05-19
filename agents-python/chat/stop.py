"""
Stop handler — EdgeOne Pages Functions
========================================

文件路径 agents/chat/stop.py 自动映射到 **POST /chat/stop**

接收 conversation_id，通过平台 runtime 的 abort 机制：
  1. 设置目标 conversation 的 cancel signal（asyncio.Event.set()）
  2. 取消对应的 asyncio.Task（抛 CancelledError）
  3. index.py 的流式循环检测到 signal 后调用 result.cancel() 终止 LLM 调用

这样 LLM 的调用会被真正中断，而不仅仅是断开 SSE 连接。
"""

from ._logger import create_logger

logger = create_logger("stop")


async def handler(context):
    """中断正在执行的 agent run。

    通过 ctx.utils.abort_active_run 触发 runtime 级别的取消：
      - 设置目标 conversation 的 asyncio.Event signal
      - cancel 对应的 asyncio.Task
      - index.py 流式循环中 context.request.is_cancelled 变为 True
      - 调用 Runner result.cancel() 真正终止 LLM 请求
    """
    body = context.request.body or {}
    conversation_id = body.get('conversation_id')
    logger.log(f"conversation_id: {conversation_id}")

    if not conversation_id:
        logger.error('conversation_id is required')
        return {
            'status_code': 400,
            'body': {
                'status': 'error',
                'message': 'conversation_id is required',
            }
        }

    # 调用平台 runtime 的 abort 机制，真正中断 LLM 调用
    result = context.utils.abort_active_run(conversation_id)
    logger.log("abort_active_run result:", {
        "aborted": result.aborted,
        "conversation_id": result.conversation_id,
        "run_id": result.run_id,
    })

    return {
        "status": "aborting" if result.aborted else "idle",
        "conversationId": result.conversation_id or conversation_id,
        "runId": result.run_id,
        "aborted": result.aborted,
    }
