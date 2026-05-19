"""
History handler — EdgeOne Pages Functions
=========================================

文件路径 agents/history/index.py 自动映射到 **POST /history**

根据前端传入的 pages-agent-conversation-id，从 ctx.store 读取历史消息，
用于页面刷新后恢复前端聊天窗口。
"""

from typing import Any


def _content_to_text(content: Any) -> str:
    """把 memory content 转成前端 Message.content 可展示的字符串。"""
    if isinstance(content, str):
        return content

    # OpenAI Agents SDK session item: {role/type, content: ...}
    if isinstance(content, dict):
        if "content" in content:
            return _content_to_text(content.get("content"))
        if "output" in content:
            return _content_to_text(content.get("output"))
        if "text" in content:
            return str(content.get("text") or "")
        return ""

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("output_text")
                if text:
                    parts.append(str(text))
        return "\n".join(part for part in parts if part)

    return str(content)


async def handler(context: Any):
    cid = context.conversation_id

    store = getattr(context, "store", None)
    if store is None:
        return {"messages": []}

    history = await store.get_messages(cid, limit=100, order="asc")

    # Single-pass: filter SDK intermediate items + group by run_id
    messages: list[dict] = []
    run_ids_seen: dict[str, dict] = {}

    for item in history:
        role = getattr(item, "role", None)
        if role not in ("user", "assistant"):
            continue

        metadata = getattr(item, "metadata", None) or {}
        if metadata.get("agent_sdk_session"):
            item_type = metadata.get("item_type")
            if item_type is not None and item_type != "message":
                continue

        content = _content_to_text(getattr(item, "content", ""))
        if not content:
            continue

        run_id = metadata.get("run_id")
        if not run_id:
            messages.append({
                "id": getattr(item, "message_id", None) or f"{role}-{getattr(item, 'created_at', 0)}",
                "role": role,
                "content": content,
                "timestamp": getattr(item, "created_at", None) or 0,
            })
            continue

        if run_id not in run_ids_seen:
            run_ids_seen[run_id] = {"user": None, "assistant": None, "order": len(run_ids_seen)}

        group = run_ids_seen[run_id]
        msg = {
            "id": getattr(item, "message_id", None) or f"{role}-{getattr(item, 'created_at', 0)}",
            "role": role,
            "content": content,
            "timestamp": getattr(item, "created_at", None) or 0,
        }
        if role == "user" and group["user"] is None:
            group["user"] = msg
        elif role == "assistant":
            group["assistant"] = msg

    for _run_id, group in sorted(run_ids_seen.items(), key=lambda x: x[1]["order"]):
        if group["user"] is not None:
            messages.append(group["user"])
        if group["assistant"] is not None:
            messages.append(group["assistant"])

    return {"conversation_id": cid, "messages": messages}
