"""

统一定义服务层的组件
ChatService组件
"""
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from Project_customer.app.schemas import CurrentUser
from Project_customer.app.services.auth import require_authorized_user
from Project_customer.app.services.chat import ChatService
from Project_customer.infrastructure.db import get_async_session

SessionDep = Annotated[AsyncSession, Depends(get_async_session)]

def get_chat_service(session: SessionDep):
    """
    获取业务服务
    :return:
    """
    return ChatService(session)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def require_user_role(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    """
    获取当前用户：用户角色校验
    :param authorization:
    :return:
    """
    return require_authorized_user(authorization, "user")


UserDep = Annotated[CurrentUser, Depends(require_user_role)]


def get_handoff_service(session: SessionDep):
    """
    获取业务服务
    :return:
    """
    return HandoffService(session)

HandoffServiceDep = Annotated[HandoffService, Depends(get_handoff_service)]

def require_staff_role(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    """
    获取当前用户：客服角色校验
    :param authorization:
    :return:
    """
    return require_authorized_user(authorization, "staff")

StaffDep = Annotated[CurrentUser, Depends(require_staff_role)]

def require_admin_role(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    """
    获取当前用户：管理员角色校验
    :param authorization:
    :return:
    """
    return require_authorized_user(authorization, "admin")

AdminDep = Annotated[CurrentUser, Depends(require_admin_role)]
