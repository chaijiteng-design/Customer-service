"""
服务端---->客户端（一定要经过序列化、fastapi解决）
客户端---->服务端（一定要经过反序列化、fastapi解决）
对象永远不可能经过网络传输
对象永远不能写入、读取到
"""
from fastapi import APIRouter
from Project_customer.app.dependencies import HandoffServiceDep, StaffDep, AdminDep
from Project_customer.app.schemas import ReplyRequest


router = APIRouter(prefix="api/v1", tags=["人工客服以及管理员指标监控的路由"])

router = APIRouter()

@router.get("/handoffs")
async def handoffs_endpoint(
    service: HandoffServiceDep,
    _: StaffDep # 只检测
):
    return await service.get_open_handoffs()

@router.get("/handoffs/{handoff_id}/messages")
async def get_handoff_messages_endpoint(
        handoff_id: str,
        service: HandoffServiceDep,
        _: StaffDep  # 只检验
):
    return await service.get_handoff_messages(handoff_id)

@router.post("/handoffs/{handoff_id}/accept")
async def accept_handoff_endpoint(
        handoff_id: str,
        service: HandoffServiceDep,
        _: StaffDep  # 只检验
):
    return await service.accept_handoff(handoff_id)

@router.post("/handoffs/{handoff_id}/messages")
async def reply_handoff_endpoint(
        handoff_id: str,
        reply: ReplyRequest,
        service: HandoffServiceDep,
        _: StaffDep  # 只检验
):
    return await service.reply_handoff(handoff_id, reply)


@router.post("/handoffs/{handoff_id}/resolve")
async def resolve_handoff_endpoint(
        handoff_id: str,
        service: HandoffServiceDep,
        _: StaffDep  # 只检验
):
    return await service.resolve_handoff(handoff_id)

@router.get("/admin/metrics")
async def get_admin_metrics_endpoint(
        service: HandoffServiceDep,
        _: AdminDep  # 只检验
):
    return await service.get_admin_metrics()


