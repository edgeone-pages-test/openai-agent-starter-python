"""
OpenAI Agents SDK session adapter for EdgeOne ctx.store.

Runner.run_streamed(..., session=session) 会自动：
  1. 调用 get_items() 读取历史并拼入本轮 input
  2. 调用 add_items() 持久化本轮 user / assistant / tool items

这个文件只做薄适配，不在业务 handler 中手动拼历史或写回回复。
"""

from __future__ import annotations

from typing import Any


_VALID_ROLES = {"user", "assistant", "system", "tool"}
_SESSION_METADATA = {"agent_sdk_session": True}


class EdgeOneSession:
    """把 EdgeOne ctx.store 适配成 OpenAI Agents SDK Session Protocol。"""

    session_settings = None

    def __init__(self, store: Any, session_id: str, max_items: int = 100):
        self.store = store
        self.session_id = session_id
        self.max_items = max_items

    async def get_items(self, limit: int | None = None) -> list[dict[str, Any]]:
        if self.store is None:
            return []

        effective_limit = min(limit or self.max_items, 100)
        messages = await self.store.get_messages(
            self.session_id,
            limit=effective_limit,
            order="asc",
        )

        items: list[dict[str, Any]] = []
        for message in messages:
            item = self._message_to_item(message)
            if item is not None:
                items.append(item)
        return items[-limit:] if limit is not None else items

    async def add_items(self, items: list[dict[str, Any]]) -> None:
        if self.store is None or not items:
            return

        for item in items:
            normalized = self._jsonable(item)
            role = self._role_for_item(normalized)
            await self.store.append_message(
                self.session_id,
                role,
                normalized,
                metadata={
                    **_SESSION_METADATA,
                    "item_type": normalized.get("type") if isinstance(normalized, dict) else None,
                },
            )

    async def pop_item(self) -> dict[str, Any] | None:
        if self.store is None:
            return None

        messages = await self.store.get_messages(self.session_id, limit=100, order="desc")
        for message in messages:
            item = self._message_to_item(message)
            if item is None:
                continue
            await self.store.delete_message(self.session_id, message.message_id)
            return item
        return None

    async def clear_session(self) -> None:
        if self.store is not None:
            await self.store.clear_messages(self.session_id)

    def _message_to_item(self, message: Any) -> dict[str, Any] | None:
        content = getattr(message, "content", None)
        role = getattr(message, "role", None)
        metadata = getattr(message, "metadata", None) or {}

        # 新数据：content 中保存完整 Agents SDK input item。
        if metadata.get("agent_sdk_session") and isinstance(content, dict):
            return content

        # 兼容旧数据：之前手动写入的 user / assistant 文本消息。
        if role in _VALID_ROLES and content is not None:
            return {"role": role, "content": content}

        return None

    @staticmethod
    def _role_for_item(item: Any) -> str:
        if isinstance(item, dict):
            role = item.get("role")
            if role in _VALID_ROLES:
                return role

            item_type = item.get("type")
            if item_type == "message":
                msg_role = item.get("role")
                return msg_role if msg_role in _VALID_ROLES else "assistant"
            if item_type in {"function_call_output", "computer_call_output"}:
                return "tool"
            if item_type in {"function_call", "computer_call", "reasoning"}:
                return "assistant"

        return "tool"

    @staticmethod
    def _jsonable(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return item
        if hasattr(item, "model_dump"):
            return item.model_dump(exclude_unset=True)
        if hasattr(item, "dict"):
            return item.dict(exclude_unset=True)
        return {"role": "tool", "content": str(item)}
