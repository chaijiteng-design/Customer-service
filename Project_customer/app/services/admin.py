from email import message
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import user, func

from Project_customer.app.models.models import Conversation, Handoff
from Project_customer.app.services.realtime import RealtimeService
from Project_customer.app.models.enums import HandoffStatus, ConversationMode, MessageRole
from Project_customer.app.models.models import Handoff, Message
from Project_customer.app.schemas import ReplyRequest
from Project_customer.common.utils import get_uid, get_utcnow


class HandoffService:

    def __init__(self, session: AsyncSession):
        self._session = session
        self._realtime_service = RealtimeService(session)

    def creat_handoff(self,
                      conversion: Conversation,
                      summary: str):
        '''
        职责：初始化工单
        :param conversion:
        :param summary:
        :return:
        '''

        handoff = Handoff(conversation_id=conversion.id,
                          user_id=conversion.user_id,
                          summary=summary,
                          status=HandoffStatus.WAITING
                          )
        self._session.add(handoff)

    async def get_open_handoffs(self) -> list[Handoff]:
        '''
        职责：查询未开放状态【WAITING/ACTIVE】
        :return:
        '''

        stmt = select(Handoff).where(Handoff.status.in_([HandoffStatus.WAITING, HandoffStatus.ACTIVE])).order_by(
            Handoff.created_at
        )
        return list((await self._session.scalars(stmt)).all())

    async def get_handoff_messages(self, handoff_id: str) -> dict[str, Any]:
        '''
        职责：获取指定工单下的会话消息
        :param handoff_id:
        :return:
        '''
        stmt = select(Message).join(Handoff, Handoff.conversation_id == Message.conversation_id).where(
            handoff_id == Handoff.id).order_by(Message.id)

        return {"messages": (await self._session.scalars(stmt)).all()}

    async def accept_handoff(self, handoff_id: str, staff_id: str):
        '''
        职责：接收工单（防止多个客服同时接收同一个工单）
        :param handoff_id:
        :param staff_id:
        :return:
        '''
        # 1、根据工单，查询工单信息
        handoff, conversion = await self._get_handoff_and_conversation(handoff_id)  

        if handoff.status == HandoffStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="该工单已经被客服接入")

        # 2、修改工单的状态以及staff_id
        handoff.status = HandoffStatus.ACTIVE
        handoff.staff_id = staff_id

        # 3、修改会话模式 HUMAN
        conversion.mode = ConversationMode.HUMAN

        # 4、保存客服接入的引导消息并实时推送事件到客户端
        self._save_human_reply(conversion, f"客服{staff_id}已经接入，请问有什么可以帮助你。")

        # 5、提交
        await self._session.commit()

    async def reply_handoff(self, handoff_id: str, payload: ReplyRequest):
        '''
        职责：只负责将客服回复的内容保存到事件表中
        :param handoff_id:
        :param payload:
        :return:
        '''
        _, conversion = await self._get_handoff_and_conversation(handoff_id)

        self._save_human_reply(conversion, payload.text)

        await self._session.commit()

    async def resolve_handoff(self, handoff_id: str):
        '''
        职责：结束工单
        :param handoff_id:
        :return:
        '''
        handoff, conversion = await self._get_handoff_and_conversation(handoff_id)

        handoff.status = HandoffStatus.RESOLVED
        conversion.mode = ConversationMode.AI

        self._save_human_reply(conversion, "人工客服服务接收，稍后由 AI 为你服务。")

        await self._session.commit()

    async def get_admin_metrics(self) -> dict[str, Any]:
        '''
        职责：获取指标信息【会话】
        :return:
        '''
        return {
            "conversations": await self._get_count(Conversation.id),
            "handoffs": await self._get_count(Handoff.id),
            "queued": await self._get_count(Conversation.id, Conversation.mode == ConversationMode.QUEUED),
            "human": await self._get_count(Conversation.id, Conversation.mode == ConversationMode.HUMAN)
        }

    async def _get_count(self, col, *condition_expr):

        return await self._session.scalar(select(func.count(col)).where(*condition_expr))

    async def _get_handoff_and_conversation(self, handoff_id):
        '''
        职责： 根据工单ID，查询工单信息和会话信息
        :param handoff_id:
        :return:
        '''
        # 1、查询工单信息
        stmt = select(Handoff).where(Handoff.id == handoff_id).with_for_update()
        handoff = await self._session.scalar(stmt)
        # 2、查询会话信息
        conversion = await self._session.scalar(
            select(Conversation).where(Conversation.id == handoff.conversation_id).with_for_update())

        return handoff, conversion

    def _save_human_reply(self,
                          conversation: Conversation,
                          text: str):
        message = Message(
            message_id=get_uid("msg"),
            conversation_id=conversation.id,
            role=MessageRole.HUMAN,
            message_type="text",
            content={"text": text}
        )
        conversation.last_active_at = get_utcnow()

        self._session.add(message)

        self._realtime_service.add_event(message, conversation, notify_user=True, notify_staff=False)


