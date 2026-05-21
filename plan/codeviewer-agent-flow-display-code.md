# 首页右侧 CodeViewer 展示代码草案

这份代码用于首页右侧 `CodeViewer` 展示，目标是**简洁表达 EdgeOne 上创建 OpenAI Agent Python 版的关键流程**，不要求直接运行。重点展示：

- `context.store`：保存用户/助手消息，支持历史恢复；
- `store.openai_session()`：注入 OpenAI Agents SDK 会话记忆；
- `@function_tool`：使用当前项目中定义的 Agent tools；
- `Agent(...)`：创建 OpenAI Agent；
- `Runner.run_streamed()`：启动 Agent。

```python
import json
from typing import Annotated

from agents import Agent, Runner, function_tool

from ._model import llm_model

INSTRUCTIONS = "..."

# 1. 展示当前项目中的一个工具实现，其余工具省略
@function_tool
def get_weather(city: Annotated[str, "The city to get weather for"]) -> str:
    """Get the current weather for a specified city."""
    # TODO

TOOLS = [
    get_weather,
    # More tools
]

async def handler(context):
    message = context.request.body.get("message", "")
    conversation_id = context.conversation_id
    store = context.store

    # 2. EdgeOne Store：保存用户消息，供历史恢复
    await store.append_message(conversation_id, "user", message)

    # 3. EdgeOne Store：注入 OpenAI Agents SDK 会话记忆
    session = store.openai_session(conversation_id)

    # 4. 创建 OpenAI Agent
    agent = Agent(
        name="EdgeOne Assistant",
        instructions=INSTRUCTIONS,
        model=llm_model,
        tools=TOOLS,
    )

    # 5. 启动 Agent，并注入 Store Session
    result = Runner.run_streamed(
        agent,
        input=message,
        session=session,
    )

    # 这里省略 SSE、text_delta、tool_called 等流式细节
    assistant_text = await collect_assistant_text(result)

    # 6. EdgeOne Store：保存助手回复，供 /history 恢复
    await store.append_message(conversation_id, "assistant", assistant_text)

    return {"answer": assistant_text}

async def collect_assistant_text(result):
    # 伪代码：消费 OpenAI Agents SDK 输出并拼接 assistant 文本
    return "..."
```

## 建议在 CodeViewer 中突出展示的流程

1. `context.store`：读写用户/助手消息；
2. `store.openai_session(conversation_id)`：为 OpenAI Agents SDK 注入会话记忆；
3. `@function_tool`：定义当前项目工具，如 `get_weather`；
4. `Agent(...)`：创建 Agent；
5. `Runner.run_streamed(agent, input, session)`：启动 Agent；
6. `store.append_message()`：保存助手回复，支持历史恢复。
