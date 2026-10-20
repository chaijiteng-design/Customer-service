from typing import Any

from app.schemas import ChatMessageRequest


class ChatService:
    """
    职责：处理聊天相关业务
    """
    async def process_chat_message(self, payload: ChatMessageRequest, user_id:str) -> dict[str, Any]:

        return {"conversation_id": "con_1112222", "mode": "AI"}