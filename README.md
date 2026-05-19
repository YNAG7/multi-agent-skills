# Multi-Agent Skills

一个基于 FastAPI、LangGraph、Skills 插件体系和 Vue 的多 Agent 对话平台。项目支持按 Skill 路由任务、动态导入 Skill 包、工具调用、会话管理、上下文压缩以及 mem0 长期记忆。

## 功能概览

- 多 Agent 路由：根据用户问题选择合适的 Skill，并支持多个 Worker 并行处理后汇总。
- Skill 管理：支持创建、上传 zip 导入、从 `skills/file` 目录导入、查看详情、启用/禁用、删除和运行时 reload。
- 工具系统：Skill 可声明本地 Python 工具，也可扩展 MCP 工具。
- 会话系统：支持会话列表、消息记录、删除会话。
- 上下文管理：用户界面保留完整聊天记录，Agent 侧使用摘要、最近 N 轮和长期记忆构造压缩上下文。
- 长期记忆：集成 mem0，本地使用 Qdrant 文件存储。
- 前端界面：Vue 3 + Vite，包含聊天、会话侧边栏、Skill Library 和导入面板。

## 目录结构

```text
.
├── agent/                  # LangGraph 多 Agent 编排
│   └── graph/
│       ├── builder.py       # 构建主图和 Worker 子图
│       ├── nodes.py         # Worker 节点和汇总节点
│       ├── router.py        # 路由节点
│       ├── select_router.py # Skill 选择逻辑
│       └── state.py         # LangGraph 状态定义
├── agent-frontend/          # Vue 前端
├── backend/                 # FastAPI 后端
│   ├── api/                 # HTTP API
│   ├── core/                # 配置和安全
│   ├── db/                  # 数据库连接和初始化
│   ├── models/              # SQLAlchemy 模型
│   ├── repositories/        # 数据访问层
│   ├── schemas/             # 请求/响应模型
│   └── services/            # 业务服务
├── config/                  # RAG、模型等配置
├── data/                    # 本地知识库数据
├── datas/                   # 运行时数据，如 checkpoint、mem0
├── model/                   # 模型工厂
├── rag/                     # RAG 相关逻辑
├── skills/                  # Skill 注册、加载和工具注入
│   └── file/                # Skill 文件夹
└── run_api.py               # 后端启动入口
```

## 运行环境

后端使用 Python，前端使用 Node.js。当前项目没有固定的 `requirements.txt`，如果在新环境部署，需要根据项目导入安装依赖。

后端关键依赖包括：

```text
fastapi
uvicorn
sqlalchemy
psycopg2
langchain
langchain-core
langchain-openai
langchain-community
langgraph
aiosqlite
mem0ai
qdrant-client
python-multipart
pyjwt
```

前端依赖在 [agent-frontend/package.json](agent-frontend/package.json) 中维护。

## 环境变量

后端配置位于 [backend/core/config.py](backend/core/config.py)。

常用环境变量：

```powershell
$env:POSTGRES_USER = "postgres"
$env:POSTGRES_PASSWORD = "root"
$env:POSTGRES_HOST = "127.0.0.1"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_DB = "agent"

$env:JWT_SECRET_KEY = "your-secret"
$env:DASHSCOPE_API_KEY = "your-dashscope-api-key"

$env:MEMORY_ENABLED = "true"
$env:MEMORY_RECENT_TURNS = "6"
$env:MEMORY_COMPRESS_THRESHOLD = "12"
$env:MEMORY_TOP_K = "5"
$env:MEM0_DIR = "datas/mem0"
```

模型默认使用 DashScope 兼容 OpenAI API，配置见 [model/factory.py](model/factory.py) 和 [config/rag.yml](config/rag.yml)。

## 启动后端

确认 PostgreSQL 可用，并已创建目标数据库，例如 `agent`。

```powershell
python run_api.py
```

默认后端地址：

```text
http://localhost:8000
```

健康检查：

```text
GET http://localhost:8000/health
```

启动时会自动执行：

- 初始化数据库表
- 加载 Skill Registry
- 注入 MCP tools
- 构建 LangGraph 多 Agent 图

## 启动前端

```powershell
cd agent-frontend
npm install
npm run dev
```

默认前端地址：

```text
http://localhost:5173
```

前端 API 地址配置在 [agent-frontend/src/api/http.ts](agent-frontend/src/api/http.ts)：

```ts
export const API_BASE_URL = 'http://localhost:8000'
```

## Skill 说明

Skill 存放在：

```text
skills/file/<skill_name>/
```

一个 Skill 至少需要：

```text
SKILL.md
```

可选文件：

```text
skill.json
scripts/tools.py
```

推荐结构：

```text
skills/file/product_support/
├── SKILL.md
├── skill.json
└── scripts/
    └── tools.py
```

`skill.json` 示例：

```json
{
  "name": "product-support",
  "description": "处理产品咨询、故障排查和使用建议。",
  "enabled": true,
  "can_be_main": true,
  "needs_time_context": false,
  "mcp_servers": {},
  "mcp_tool_allowlist": []
}
```

Skill 导入支持：

- 上传 `.zip` 包
- 从 `skills/file` 下已有目录导入
- 通过 Prompt 创建简单 Skill

导入 zip 时会校验：

- 必须包含 `SKILL.md`
- Skill 名称合法
- 防止 zip slip 路径穿越
- 防止覆盖已有 Skill
- Python 工具文件位置合法
- 工具加载失败时不会拖垮整个系统

## 上下文与记忆机制

项目把“用户看到的聊天记录”和“Agent 看到的上下文”分开处理。

用户看到：

```text
chat_messages
```

这里保留完整原始聊天记录，前端聊天窗口读取这里。

Agent 看到：

```text
mem0 长期记忆
+ chat_thread_summaries 当前会话摘要
+ chat_messages 最近 N 轮原文
+ 当前用户问题
```

相关逻辑在：

- [backend/services/context_service.py](backend/services/context_service.py)
- [backend/services/chat_service.py](backend/services/chat_service.py)
- [backend/services/mem0_service.py](backend/services/mem0_service.py)

默认策略：

```text
MEMORY_RECENT_TURNS = 6
MEMORY_COMPRESS_THRESHOLD = 12
MEMORY_TOP_K = 5
```

含义：

- Agent 保留最近 6 轮完整对话
- 超过 12 轮后压缩旧历史到 `chat_thread_summaries`
- 每次检索最多取 5 条 mem0 长期记忆

LangGraph checkpoint 仍按会话保存，但每次请求入口会清空旧 `messages`，再注入压缩后的上下文，避免完整历史无限进入模型上下文。

## mem0 数据位置

mem0 本地目录：

```text
datas/mem0
```

主要内容：

```text
datas/mem0/qdrant      # 向量记忆库
datas/mem0/history.db  # mem0 历史记录
```

如果后端正在运行，本地 Qdrant 目录可能被占用。此时不要在另一个进程里再次打开同一个本地 Qdrant 存储。可以停掉后端后再用 mem0 API 查看，或者后续添加一个只读调试接口。

## 主要 API

认证：

```text
POST /auth/register
POST /auth/login
GET  /users/me
```

聊天：

```text
POST   /chat
GET    /chat/sessions
GET    /chat/sessions/{thread_id}/messages
DELETE /chat/sessions/{thread_id}
```

Skill：

```text
GET    /skills
POST   /skills
POST   /skills/import/zip
POST   /skills/import/zip/preview
POST   /skills/import/directory
POST   /skills/reload
GET    /skills/tools
GET    /skills/{skill_name}
PATCH  /skills/{skill_name}/enabled
DELETE /skills/{skill_name}
```

## 开发常用命令

后端语法检查：

```powershell
python -m py_compile backend\services\agent_service.py backend\services\chat_service.py agent\graph\state.py
```

前端构建：

```powershell
cd agent-frontend
npm run build
```

查看 Git 状态：

```powershell
git status --short
```

## 常见问题

### 后端启动时报数据库连接失败

检查 PostgreSQL 是否启动，数据库名、账号、密码是否和环境变量一致。

### mem0 报 Qdrant 目录被占用

本地 Qdrant 文件存储不适合多进程同时打开。同一时间只让一个后端进程访问 `datas/mem0/qdrant`。如果要多进程访问，建议改成独立 Qdrant Server。

### Agent 回复重复或混入上一轮结果

确认 [backend/services/agent_service.py](backend/services/agent_service.py) 中请求入口会清空旧 `messages`，并且 [agent/graph/state.py](agent/graph/state.py) 中 `agent_results` 使用了支持 reset 的 reducer。

### 前端请求 401

登录态保存在 `localStorage.access_token`。重新登录或清理浏览器 localStorage。

### Skill 修改后没有生效

调用：

```text
POST /skills/reload
```

或者在前端 Skill Library 中点击刷新/重载。

## 数据文件说明

运行时会产生以下文件或目录：

```text
datas/chat_multi_history.db   # LangGraph checkpoint
datas/mem0/                   # mem0 本地记忆
chroma_db/                    # Chroma/RAG 向量库
logs/                         # 日志
```

这些文件属于运行时数据，不建议手动修改。需要重置时应先停止后端服务。
