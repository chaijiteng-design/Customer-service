# 电商客服服务（Project_customer）

基于 FastAPI 的电商客服后端，提供用户聊天、AI 自动回复、人工客服转接及实时消息推送。消息与处理状态保存在 PostgreSQL 中，后台 Worker 调用 AI 服务，并通过 Redis Pub/Sub 和 WebSocket 向客户端发送通知。

本文对应当前源码实现。项目依赖文件位于本目录的上一级 `Customer-service/`，以下命令均在该目录执行。

## 功能

- 用户发送文本或对象消息，通过 `message_id` 检查重复消息，查询历史记录。
- AI 模式下将短时间内的消息归入同一轮次，默认收集窗口为 800 毫秒。
- AI Worker 异步领取轮次，携带最近最多 30 条历史消息调用外部 AI 服务；支持失败重试和过期回复丢弃。
- AI 返回转人工结果后创建工单；客服可查看、接入、回复和结束工单，结束后恢复 AI 模式。
- 实时事件先随业务数据写入数据库，再由 Realtime Worker 发布到 Redis，API 通过 WebSocket 转发。
- 使用 JWT 区分 `user`、`staff`、`admin` 三类身份，提供管理员统计接口。
- 提供本地 Mock AI，方便联调普通回复和转人工流程。

## 技术栈

Python 3.12+、FastAPI、Uvicorn、Pydantic Settings、SQLAlchemy 2.x、psycopg、PostgreSQL、Redis、HTTPX、PyJWT。依赖约束见上一级 `pyproject.toml`，锁定版本见 `uv.lock`；使用 uv 管理依赖。

## 目录结构

```text
Customer-service/
├── pyproject.toml
├── uv.lock
├── .env                         # 当前配置类实际读取的位置
└── Project_customer/
    ├── README.md
    ├── main.py                  # API 启动入口，使用自定义事件循环
    ├── app/
    │   ├── app.py               # FastAPI 应用、路由与 CORS
    │   ├── dependencies.py      # 数据库、业务服务和角色校验依赖
    │   ├── schemas.py           # 请求模型与用户身份模型
    │   ├── models/              # ORM 模型与状态枚举
    │   ├── routers/             # 聊天、人工客服、统计、WebSocket
    │   ├── services/            # 聊天、认证、工单及实时事件业务
    │   └── worker/              # AI Worker 与 Realtime Worker
    ├── common/                  # 配置、事件循环、ID 和时间工具
    ├── infrastructure/          # PostgreSQL、Redis、数据库初始化
    ├── mock_ai/                 # 本地模拟 AI 服务
    └── test/                    # ORM 与 Redis Pub/Sub 演示脚本
```

## 快速开始

### 1. 准备环境与依赖

准备 Python 3.12 或更高版本、uv、PostgreSQL 和 Redis。数据库使用 PostgreSQL 的 JSONB 与部分唯一索引，不适合直接替换为 SQLite。

```powershell
cd D:\Code\GoShop\Customer-service
uv sync
```

### 2. 配置环境变量

编辑 `Customer-service/.env`。`common/settings.py` 通过文件位置定位该文件，系统环境变量可覆盖同名配置。以下为本地开发示例，数据库、账号和密码需自行创建并替换：

```dotenv
DATABASE_URL=postgresql+psycopg://customer_service:replace-me@127.0.0.1:5432/customer_service
JWT_SECRET=replace-with-your-local-secret
JWT_ALGORITHM=HS256
API_HOST=127.0.0.1
API_PORT=8001
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173","http://localhost:5174","http://127.0.0.1:5174"]
CONVERSATION_IDLE_TIMEOUT_MINUTES=30
MESSAGE_MERGE_DELAY_MS=800
INTERNAL_SERVICE_TOKEN=replace-with-your-internal-token
AI_SERVICE_URL=http://127.0.0.1:8002
AI_TIMEOUT_SECONDS=30
AI_WORKER_POLL_INTERVAL_MS=100
AI_WORKER_MAX_ATTEMPTS=3
AI_WORKER_RETRY_DELAY_SECONDS=2
REDIS_URL=redis://127.0.0.1:6379/0
REALTIME_WORKER_POLL_INTERVAL_SECONDS=1
```

**Redis 配置的当前限制：** `infrastructure/redis.py` 直接使用 `192.168.200.128:6379`、数据库 `0` 创建客户端，尚未使用 `REDIS_URL`。连接其他 Redis 实例时，需要修改该文件中的客户端连接参数；仅修改 `.env` 不会改变实际连接地址。

`JWT_SECRET` 应与签发用户令牌的服务一致。`INTERNAL_SERVICE_TOKEN` 会通过请求头传给 AI 服务；真实 AI 服务需按自身协议配置校验。

### 3. 创建数据库表

先在 PostgreSQL 中创建配置指向的数据库，并确保连接账号有建表权限。

**注意：当前初始化脚本会依次执行 `drop_all` 和 `create_all`，删除并重建本服务模型声明的表，已有业务数据会丢失。下面的命令仅用于空库或允许重置的开发库，不是增量迁移命令。**

```powershell
uv run python -m Project_customer.infrastructure.init_db
```

### 4. 启动服务

分别打开四个终端，每个终端都切换到 `Customer-service/`，运行以下对应命令：

| 进程 | 命令 | 作用 |
| --- | --- | --- |
| Mock AI | `uv run python -m Project_customer.mock_ai.app` | 在 8002 端口模拟 AI；已有真实 AI 服务时可省略 |
| API | `uv run python -m Project_customer.main` | 默认监听 8001 端口 |
| AI Worker | `uv run python -m Project_customer.app.worker.ai` | 处理数据库中的待执行 AI 轮次 |
| Realtime Worker | `uv run python -m Project_customer.app.worker.realtime` | 将待发布事件推送到 Redis |

**API 当前不会自动启动两个 Worker，必须分别运行。** `app/app.py` 中的 lifespan 没有绑定到 FastAPI 实例，且启动 Worker 的代码仍被注释。

Windows 下建议使用上面的模块启动命令。API 和两个 Worker 的入口通过 `common/event_loop.py` 使用 SelectorEventLoop，适配 psycopg 异步连接。

API 启动后可访问：

- 健康检查：[http://127.0.0.1:8001/hello](http://127.0.0.1:8001/hello)，返回 `{"status":"ok"}`。
- Swagger 文档：[http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)。
- ReDoc 文档：[http://127.0.0.1:8001/redoc](http://127.0.0.1:8001/redoc)。

`/hello` 仅检查 API 是否响应，不校验数据库、Redis 或 Worker 是否可用。

## 身份认证与接口

HTTP 业务接口使用请求头 `Authorization: Bearer <JWT>`。令牌载荷包含 `user_id` 和 `role`，角色值为小写 `user`、`staff`、`admin`。当前没有登录或签发令牌的 HTTP 接口。

本地联调可在项目根目录生成用户令牌：

```powershell
$userToken = uv run python -c 'from Project_customer.app.schemas import CurrentUser; from Project_customer.app.services.auth import encode_token; print(encode_token(CurrentUser(user_id="user_001", role="user")))'
```

生成客服或管理员令牌时，替换 `user_id`，将 `role` 改为 `staff` 或 `admin`。此辅助函数只写入用户 ID 和角色，没有自动添加有效期。

| 方法 | 路径 | 身份 | 说明 |
| --- | --- | --- | --- |
| GET | `/hello` | 无 | API 响应检查 |
| POST | `/api/v1/chat/messages` | user | 接收消息；成功返回 204，无响应体 |
| GET | `/api/v1/chat/history` | user | 查询当前用户历史与当前会话 |
| GET | `/api/v1/handoffs` | staff | 查询 WAITING、ACTIVE 工单 |
| GET | `/api/v1/handoffs/{handoff_id}/messages` | staff | 查询工单关联消息 |
| POST | `/api/v1/handoffs/{handoff_id}/accept` | staff | 接入工单，无请求体 |
| POST | `/api/v1/handoffs/{handoff_id}/messages` | staff | 回复，JSON 请求体为 `{"text":"您好"}` |
| POST | `/api/v1/handoffs/{handoff_id}/resolve` | staff | 结束工单并恢复 AI 模式，无请求体 |
| GET | `/api/v1/admin/metrics` | admin | 统计接口，当前存在下文说明的实现问题 |
| WebSocket | `/api/v1/realtime` | JWT | 建立连接后发送 token 认证 |

HTTP 角色按表中的值精确匹配，管理员身份不会自动获得用户或客服接口权限。

### 发送消息与查询历史

```powershell
$headers = @{ Authorization = "Bearer $userToken" }
$body = @{
    message_id = "msg_$([guid]::NewGuid().ToString('N'))"
    type = "text"
    content = @{ text = "你好，我想咨询商品" }
} | ConvertTo-Json -Depth 5

Invoke-WebRequest -Method Post -Uri 'http://127.0.0.1:8001/api/v1/chat/messages' -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/v1/chat/history' -Headers $headers
```

`message_id` 应全局唯一；重发同一消息时复用该 ID。`type` 支持 `text` 和 `object`，`content` 为 JSON 对象；文本消息使用 `content.text`。消息提交后异步处理，204 不代表 AI 已回复，可通过实时连接接收结果或稍后查询历史。

历史接口的当前响应结构如下，其中 `conversations` 字段实际表示当前会话模式：

```json
{
  "chat_history": {
    "current_conversation": "conv_...",
    "conversations": "AI",
    "messages": [
      {
        "conversation_id": "conv_...",
        "role": "USER",
        "content": {"text": "你好，我想咨询商品"}
      }
    ]
  }
}
```

### WebSocket 实时消息

连接 `ws://127.0.0.1:8001/api/v1/realtime` 后，第一条客户端消息必须是：

```json
{"token":"<JWT>"}
```

这里传原始 JWT，不带 `Bearer `。认证并订阅成功后，服务端发送 `{"event_type":"connected"}`。普通业务事件示例：

```json
{
  "conversation_mode": "AI",
  "role": "AI",
  "content": {"reply_type":"ANSWER","text":"您好，请问有什么可以帮助您？"}
}
```

用户按 `user_id` 订阅 Redis 通道；当前实现中，其他合法角色订阅公共 `staff` 通道。普通业务事件没有统一的 `event_type` 字段。Redis Pub/Sub 不保存离线订阅消息，客户端重新连接后可通过历史或工单接口刷新数据。

### 转人工联调

1. 启动 Mock AI、API 和两个 Worker，用户先建立 WebSocket 连接。
2. 用户发送包含“我要转人工”的文本，Mock AI 返回 `REQUEST_HANDOFF`。
3. 等待 AI Worker 处理后，会话变为 `QUEUED`，工单状态为 `WAITING`。
4. 使用客服令牌查询工单列表并调用 `accept`，会话变为 `HUMAN`，工单变为 `ACTIVE`。
5. 客服调用工单消息接口回复，用户通过 WebSocket 或历史接口查看。
6. 客服调用 `resolve`，工单变为 `RESOLVED`，会话恢复 `AI`。

## 数据与处理流程

| 数据表 | 用途 |
| --- | --- |
| `conversations` | 用户会话、模式与活跃时间 |
| `messages` | 用户、AI、人工消息及唯一业务消息 ID |
| `conversation_turns` | AI 轮次、收集截止时间、消息快照和尝试次数 |
| `handoffs` | 人工工单、摘要、处理客服与状态 |
| `realtime_events` | 实时事件、目标通道及发布时间 |

```text
用户发送消息 → API 写入消息与轮次 → AI Worker 调用 AI 服务
                                           ↓
                            保存回复 / 创建人工工单
                                           ↓
                           同一业务事务写入 realtime_events
                                           ↓
Realtime Worker → Redis Pub/Sub → API WebSocket → 客户端
```

AI 模式会话默认空闲 30 分钟后失效，在读取或发送消息时检查并新建会话；排队和人工模式不走该空闲关闭逻辑。轮次状态包括 `COLLECTING`、`RUNNING`、`COMPLETED`、`FAILED`、`SUPERSEDED`；如果 AI 调用期间有新用户消息，旧快照结果会被丢弃。

## 当前限制与排查

- **发出消息但没有 AI 回复：** 检查 AI Worker、AI 服务和数据库连接；只启动 API 不会处理轮次。
- **历史里有回复但没有实时通知：** 检查 Realtime Worker、实际 Redis 连接地址和 WebSocket 首条认证消息。
- **管理员统计接口：** 当前 `get_admin_metrics()` 中 `queued`、`human` 的查询条件传入了元组，可能导致 SQLAlchemy 参数错误，需要修正后再使用。
- **工单接口边界：** 当前主要校验客服角色，尚未完整校验工单归属、状态流转和工单不存在的情况。
- **测试现状：** `test/orm.py` 和 `test/pub_sub.py` 是手动演示脚本，会访问外部数据库或 Redis；目前没有完整的自动化业务测试。Pub/Sub 演示脚本有独立的硬编码 Redis 地址。
- **部署前配置：** 替换默认密钥、令牌及内网连接参数；目前未提供数据库增量迁移和统一多进程启动配置。

本说明基于源码整理；实际端到端运行还取决于本地 PostgreSQL、Redis、AI 服务及配置。
