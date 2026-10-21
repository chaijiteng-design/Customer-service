from enum import StrEnum


class ConversationMode(StrEnum):
    '''
    会话模式
    AI: 机器人模式
    '''
    AI = "AI"  # 机器人模式
    QUEUED = "QUEUED"  # 队列模式
    CLOSED = "CLOSED"  # 关闭模式


class MessageRole(StrEnum):
    '''
    消息角色
    '''
    USER = "USER"  # 用户角色
    AI = "AI"  # 机器人角色
    HUMAN = "HUMAN"  # 人类角色


class TurnStatus(StrEnum):
    '''
    轮次状态
    '''
    COLLECTING = "COLLECTING"  # 收集中
    RUNNING = "RUNNING"  # 运行中
    COMPLETED = "COMPLETED"  # 完成
    FAILED = "FAILED"  # 失败
    SUPERSEDED = "SUPERSEDED"  # 过期
