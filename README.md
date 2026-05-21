# Multi-Agent Skills

基于 FastAPI、LangGraph、Skills 插件体系和 Vue 3 的多 Agent 对话平台。项目支持按 Skill 路由任务、并发 Worker 执行、工具调用、Skill 动态导入、会话管理、上下文压缩、mem0 长期记忆，以及管理员运行监控。

## 功能概览

- 多 Agent 路由：Router 根据用户输入选择一个或多个 Skill，并分发给 Worker 执行。
- Skill 管理：支持创建、上传 zip 导入、从 `skills/file` 目录导入、查看详情、启用/禁用、删除和运行时 reload。
- 工具系统：Skill 可声明本地 Python 工具，也可扩展远端 MCP 工具。
- 会话系统：支持会话列表、消息记录、删除会话和流式回复。
- 上下文管理：前端保留完整聊天记录，Agent 侧使用最近 N 轮、会话摘要和 mem0 长期记忆构造压缩上下文。
- 长期记忆：集成 mem0，本地使用 Qdrant 文件存储。
- 运行监控：管理员可查看 run、router 分配、worker 输出、工具调用、最终输出和耗时。
- 前端界面：Vue 3 + Vite，包含聊天页、Skill Library、Skill 导入面板和管理员监控页。

## 目录结构

```text
.
├── agent/                  # LangGraph 多 Agent 编排
│   └── graph/
│       ├── builder.py       # 构建主图和 Worker 子图
│       ├── nodes.py         # Worker 节点和 Summarizer 节点
│       ├── router.py        # Router 节点
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

后端使用 Python，前端使用 Node.js。当前仓库没有固定的 `requirements.txt`，如果在新环境部署，需要根据项目导入安装依赖。

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

前端依赖维护在 [agent-frontend/package.json](agent-frontend/package.json)。

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

$env:ADMIN_USERNAMES = "admin"
```

mem0 默认使用 DashScope 兼容 OpenAI API：

```powershell
$env:MEM0_LLM_PROVIDER = "openai"
$env:MEM0_LLM_MODEL = "qwen-turbo"
$env:MEM0_LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:MEM0_LLM_API_KEY = $env:DASHSCOPE_API_KEY

$env:MEM0_EMBEDDER_PROVIDER = "openai"
$env:MEM0_EMBEDDER_MODEL = "text-embedding-v4"
$env:MEM0_EMBEDDER_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:MEM0_EMBEDDER_API_KEY = $env:DASHSCOPE_API_KEY
$env:MEM0_COLLECTION_NAME = "mem0"
$env:MEM0_EMBEDDING_DIMS = "1024"
```

监控落库策略：

```powershell
# 默认 false：只存关键节点，避免 prompt/messages 反复落库
$env:MONITOR_STORE_RAW_EVENTS = "false"

# 默认 false：不额外从 worker messages 中补抓 observed tool，避免工具调用重复
$env:MONITOR_CAPTURE_OBSERVED_TOOLS = "false"
```

第三方遥测和 HuggingFace symlink 警告已在 [backend/services/mem0_service.py](backend/services/mem0_service.py) 中默认关闭：

```text
MEM0_TELEMETRY=False
DISABLE_TELEMETRY=1
HF_HUB_DISABLE_TELEMETRY=1
HF_HUB_DISABLE_SYMLINKS_WARNING=1
```

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

如果 PowerShell 拦截 `npm.ps1`，可改用：

```powershell
npm.cmd run dev
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
- 工具加载失败时不拖垮整个系统

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

相关逻辑：

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

## 运行监控

管理员用户可以打开监控页查看运行链路。管理员由环境变量 `ADMIN_USERNAMES` 控制，默认包含 `admin`。

监控数据表：

```text
agent_runs        # 一次用户请求的输入、输出、状态、耗时、主 skill
agent_run_steps   # 关键执行节点
agent_tool_calls  # 工具调用
```

默认只存关键节点：

- Router 任务分配
- Worker 开始
- Worker 结束
- Worker 异常
- 工具调用单独进入 `agent_tool_calls`
- Summarizer 输出直接使用 `agent_runs.output`

这样可以避免把同一份 prompt、messages、model input/output 在每个 LangChain 原始事件中重复落库。需要排查底层事件时，可临时启用：

```powershell
$env:MONITOR_STORE_RAW_EVENTS = "true"
```

监控 API：

```text
GET /monitor/summary
GET /monitor/runs
GET /monitor/runs/{run_id}
```

返回详情里包含：

```text
run         # 本次请求摘要
steps       # 关键节点
tool_calls  # 工具调用
trace       # 前端展示用执行链路
```

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

如果后端正在运行，本地 Qdrant 目录可能被占用。不要在另一个进程里同时打开同一个本地 Qdrant 存储。需要多进程访问时，建议改成独立 Qdrant Server。

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

监控：

```text
GET /monitor/summary
GET /monitor/runs
GET /monitor/runs/{run_id}
```

## 开发常用命令

后端语法检查：

```powershell
python -m compileall backend agent
```

也可以只检查单个文件：

```powershell
python -m compileall backend\services\agent_service.py backend\api\monitor_api.py
```

前端构建：

```powershell
cd agent-frontend
npm.cmd run build
```

查看 Git 状态：

```powershell
git status --short
```

## 常见问题

### 后端启动时报数据库连接失败

检查 PostgreSQL 是否启动，数据库名、账号、密码是否和环境变量一致。

### mem0 报 Qdrant 目录被占用

本地 Qdrant 文件存储不适合多进程同时打开。同一时间只让一个后端进程访问 `datas/mem0/qdrant`。如果需要多进程访问，建议改成独立 Qdrant Server。

### 启动时出现 PostHog SSL 上传错误

这是 mem0 匿名遥测，不是业务请求。项目已默认设置 `MEM0_TELEMETRY=False` 关闭上传。重启后端后生效。

### HuggingFace 提示 Windows 不支持 symlink

这是缓存系统降级提示，不影响下载和运行。项目已默认设置 `HF_HUB_DISABLE_SYMLINKS_WARNING=1` 压掉警告。需要真正启用 symlink 可开启 Windows Developer Mode 或用管理员权限运行 Python。

### Router 里显示重复的 base-assistant

这是监控 trace 解析重复提取任务导致的显示问题，不代表真的执行了两个 Worker。`monitor_api.py` 已对 `(skill, sub_task)` 做去重。

### Agent 回复重复或混入上一轮结果

确认 [backend/services/agent_service.py](backend/services/agent_service.py) 中请求入口会清空旧 `messages`，并且 [agent/graph/state.py](agent/graph/state.py) 中 `agent_results` 使用了支持 reset 的 reducer。

### 前端请求 401

登录态保存在 `localStorage.access_token`。重新登录或清理浏览器 localStorage。

### Skill 修改后没有生效

调用：

```text
POST /skills/reload
```

也可以在前端 Skill Library 中点击刷新/重载。

## 运行时数据

运行时会产生以下文件或目录：

```text
datas/chat_multi_history.db   # LangGraph checkpoint
datas/mem0/                   # mem0 本地记忆
chroma_db/                    # Chroma/RAG 向量库
logs/                         # 日志
agent-frontend/dist/          # 前端构建产物
```

这些文件属于运行时数据，不建议手动修改。需要重置时应先停止后端服务。
