# Multi-Agent Skills

一个基于 **FastAPI + LangGraph + Vue 3** 的多 Agent 对话平台。项目的核心目标是：

- 用 Skill 体系管理不同能力模块。
- 用 Router 自动选择合适 Skill，并由 Worker 执行。
- 支持管理员查看运行监控、管理知识库、上传文档、重建索引和做 RAGAS 测评。
- 支持 mem0 长期记忆、会话摘要、RAG 检索增强和在线 Skill 编辑。

当前项目更像一个“可管理的 Agent 工作台”，不是单纯聊天 Demo。

## 功能概览

### 对话与 Agent 编排

- LangGraph 构建多 Agent 执行图。
- Router 根据用户问题选择一个或多个 Skill。
- Worker 根据 Skill 描述、工具和上下文生成结果。
- 支持流式输出。
- 支持会话列表、历史消息、删除会话。
- Agent 输入上下文经过压缩，不会把完整历史无限塞进模型。

### Skill 管理

- 独立 Skill 页面。
- 只展示已添加 Skill。
- 新增 Skill 必须点击新增按钮，并在弹窗中完成。
- 新增支持 zip 上传和在线输入切换。
- `SKILL.md` 支持在线输入。
- `skill.json` 支持在线输入，并提供常用字段。
- 已添加 Skill 支持在线修改、启用/禁用、删除、重新加载。

### 知识库与 RAG

- 管理员可见知识库页面。
- 支持前端上传 `txt/pdf` 到 RAG。
- 支持同步 `data/` 目录。
- 支持文档列表、详情、重建索引、删除。
- 文档元数据写入 PostgreSQL。
- 向量索引使用 Chroma。
- 文档变更使用 `path + mtime + size` 预检查，变更后再计算 SHA-256。
- 支持父子切块：子块用于向量检索，召回后扩展为父块上下文。
- TXT/PDF 有统一解析和清洗流程。
- RAG 服务在后端启动时预热，降低第一次调用延迟。

### RAGAS 测评

- 管理员可在知识库页面点击 `RAG 测评` 按钮打开测评弹窗。
- 测评输入为 JSONL，每行一个 JSON。
- 当前支持字段：`question` 和 `reference`。
- 一次最多 20 条。
- 输出指标包含：
  - `faithfulness`
  - `answer_relevancy`
  - `context_precision`
  - `context_recall`
- 每条样本可点击查看召回上下文片段。
- 也支持命令行脚本测评。

### 监控

- 管理员可见监控页面。
- 查看 Agent run、router 分配、worker 输出、工具调用、最终输出和耗时。
- 支持删除监控记录。
- 默认只存关键节点，避免大量 prompt/messages 重复落库。

### 记忆

- 集成 mem0 长期记忆。
- 本地默认使用 Qdrant 文件存储。
- 支持最近 N 轮原文 + 会话摘要 + 长期记忆组合上下文。

## 技术栈

后端：

- FastAPI
- SQLAlchemy
- PostgreSQL
- LangChain
- LangGraph
- Chroma
- mem0
- DashScope / OpenAI Compatible API
- RAGAS

前端：

- Vue 3
- Vite
- TypeScript
- lucide-vue-next
- markdown-it
- DOMPurify

## 目录结构

```text
.
├── agent/                    # LangGraph Agent 编排
│   ├── graph/                # Router、Worker、状态和图构建
│   └── tools/                # Agent 公共工具
├── agent-frontend/           # Vue 3 前端
│   └── src/
│       ├── api/              # 前端 API 封装
│       ├── pages/            # Chat、Skill、Monitor、Knowledge 页面
│       └── types/            # 前端类型
├── backend/                  # FastAPI 后端
│   ├── api/                  # HTTP API
│   ├── core/                 # 配置、安全
│   ├── db/                   # 数据库连接和初始化
│   ├── models/               # SQLAlchemy 模型
│   ├── repositories/         # 数据访问层
│   ├── schemas/              # 请求/响应模型
│   └── services/             # 业务服务
├── config/                   # 模型、RAG、Chroma、Prompt 配置
├── data/                     # 本地知识库目录
│   └── uploads/              # 前端上传的知识库文件
├── datas/                    # 运行时数据，如 mem0、checkpoint
├── eval/                     # RAGAS 测试集和结果
├── model/                    # 模型工厂
├── rag/                      # RAG 解析、切块、索引、检索
├── scripts/                  # 命令行脚本
├── skills/                   # Skill 注册与文件目录
│   └── file/                 # 本地 Skill
└── run_api.py                # 后端启动入口
```

## 快速启动

### 1. 准备数据库

项目使用 PostgreSQL。先确认 PostgreSQL 已启动，并创建数据库，例如：

```sql
CREATE DATABASE agent;
```

### 2. 配置环境变量

PowerShell 示例：

```powershell
$env:POSTGRES_USER = "postgres"
$env:POSTGRES_PASSWORD = "root"
$env:POSTGRES_HOST = "127.0.0.1"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_DB = "agent"

$env:JWT_SECRET_KEY = "your-secret"
$env:DASHSCOPE_API_KEY = "your-dashscope-api-key"

$env:ADMIN_USERNAMES = "admin"
```

`ADMIN_USERNAMES` 控制管理员账号，只有管理员能看到知识库和监控页面。

### 3. 启动后端

```powershell
python run_api.py
```

默认地址：

```text
http://localhost:8000
```

健康检查：

```text
GET http://localhost:8000/health
```

后端启动时会自动：

- 初始化数据库表。
- 补齐部分历史表字段。
- 预热 RAG 服务。
- 加载 Skill。
- 初始化 LangGraph Agent。

### 4. 启动前端

```powershell
cd agent-frontend
npm install
npm.cmd run dev
```

默认地址：

```text
http://localhost:5173
```

前端 API 地址在：

```text
agent-frontend/src/api/http.ts
```

默认指向：

```text
http://localhost:8000
```

## 关键配置

### 后端配置

主要配置在：

```text
backend/core/config.py
```

常用环境变量：

```powershell
$env:MEMORY_ENABLED = "true"
$env:MEMORY_RECENT_TURNS = "6"
$env:MEMORY_COMPRESS_THRESHOLD = "12"
$env:MEMORY_TOP_K = "5"
$env:MEM0_DIR = "datas/mem0"

$env:MONITOR_STORE_RAW_EVENTS = "false"
$env:MONITOR_CAPTURE_OBSERVED_TOOLS = "true"
```

### 模型配置

模型名称在：

```text
config/rag.yml
```

当前默认：

```yaml
smart_chat_model_name: qwen3-max
cheap_chat_model_name: qwen-turbo
embedding_model_name: text-embedding-v4
reranker_model_name: BAAI/bge-reranker-v2-m3
```

聊天模型通过 DashScope OpenAI Compatible API 调用：

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

如果本机没有开代理也能正常访问阿里云模型，这是正常的。项目里的聊天模型客户端已设置 `trust_env=False`，会避开系统代理环境变量，减少 `127.0.0.1:xxxx` 代理端口拒绝连接的问题。

### RAG 配置

RAG 和 Chroma 配置在：

```text
config/chroma.yml
```

当前关键配置：

```yaml
collection_name: agent
persist_directory: chroma_db
k: 3
top_n: 2
data_path: data
upload_path: data/uploads
allow_knowledge_file_type: ["txt", "pdf"]

parent_chunk_size: 1200
parent_chunk_overlap: 120
child_chunk_size: 360
child_chunk_overlap: 80
```

含义：

- `data_path`：本地知识库目录。
- `upload_path`：前端上传文件保存目录。
- `k`：向量初始召回数量。
- `top_n`：rerank 后最终保留数量。
- `parent_chunk_*`：父块大小，用于返回给模型。
- `child_chunk_*`：子块大小，用于向量检索。

## RAG 索引机制

当前 RAG 流程：

1. 扫描 `data/` 和上传文件。
2. 用 `path + mtime + size` 判断文件是否可能变化。
3. 文件变化后计算 SHA-256。
4. 解析文档内容。
5. 清洗文本。
6. 父子切块。
7. 子块写入 Chroma 向量库。
8. 文档、父块、子块元数据写入 PostgreSQL。
9. 检索时先召回子块，再扩展到父块作为回答上下文。

为什么不用 MD5：

- 当前文档内容哈希使用 SHA-256。
- MD5 不是不能用来做普通去重，但已经不适合作为长期内容指纹的首选。
- Milvus/Chroma 负责向量检索，不负责判断文件是否变化；文件变化判断仍应由数据库元数据和内容哈希完成。

## 文档解析与清洗

解析逻辑在：

```text
rag/document_parser.py
```

当前支持：

- TXT：编码探测、文本归一化。
- PDF：优先使用 PyMuPDF，必要时可扩展其他解析器。
- 清洗：压缩空白、合并断行、去除短噪声、保留页码 metadata。

切块逻辑在：

```text
rag/chunker.py
```

当前使用父子切块：

- 子块更短，适合向量召回。
- 父块更完整，适合给模型回答。
- `chunk_hash` 基于清洗后的 chunk 文本。

## 知识库页面

知识库页面仅管理员可见。

支持功能：

- 上传 `txt/pdf`。
- 同步 `data/`。
- 查看文档状态、大小、chunk 数、SHA-256、索引时间。
- 重建单个文档索引。
- 删除文档、chunk 和向量记录。
- 打开 RAGAS 测评弹窗。
- 点击测评样本里的召回上下文，查看具体片段。

相关 API：

```text
GET    /knowledge
POST   /knowledge/upload
POST   /knowledge/sync
POST   /knowledge/evaluate
POST   /knowledge/{document_id}/reindex
DELETE /knowledge/{document_id}
```

## RAGAS 测评

### 前端测评

管理员进入知识库页面，点击右上角：

```text
RAG 测评
```

输入 JSONL：

```json
{"question":"机器人无法连接 WiFi 时应该检查什么？","reference":"应确认手机和机器人连接同一 2.4G 网络，检查 WiFi 密码、WiFi 模块遮挡情况，重启路由器和机器人后重新绑定。"}
{"question":"拖地不出水时怎么办？","reference":"应检查水箱是否有水、出水量是否调至最低、出水管是否堵塞；加水、调高出水量，并疏通出水管。"}
```

字段说明：

- `question`：评测问题。
- `reference`：标准答案。

当前一次最多 20 条。

示例测试集：

```text
eval/rag_robot_eval.jsonl
```

### 命令行测评

脚本：

```text
scripts/evaluate_rag.py
```

运行：

```powershell
python scripts/evaluate_rag.py --input eval/rag_robot_eval.jsonl --sync
```

只收集样本，不跑 RAGAS 指标：

```powershell
python scripts/evaluate_rag.py --input eval/rag_robot_eval.jsonl --collect-only
```

输出默认保存到：

```text
eval/results/
```

指标解释：

- `faithfulness`：回答是否忠实于召回上下文。
- `answer_relevancy`：回答是否贴合问题。
- `context_precision`：召回上下文中有用片段比例。
- `context_recall`：标准答案需要的信息是否被召回。

## Skill 体系

Skill 存放在：

```text
skills/file/<skill_name>/
```

一个 Skill 至少需要：

```text
SKILL.md
```

推荐结构：

```text
skills/file/customer_service/
├── SKILL.md
├── skill.json
└── scripts/
    └── tools.py
```

`skill.json` 示例：

```json
{
  "name": "customer-service",
  "description": "处理售后咨询、投诉处理和服务流程说明。",
  "enabled": true,
  "can_be_main": true,
  "needs_time_context": false,
  "mcp_servers": {},
  "mcp_tool_allowlist": []
}
```

常用字段：

- `name`：Skill 名称。
- `description`：用于 Router 判断是否应该选择该 Skill。
- `enabled`：是否启用。
- `can_be_main`：是否可以作为主 Skill。
- `needs_time_context`：是否需要时间上下文。
- `mcp_servers`：远端 MCP 服务配置。
- `mcp_tool_allowlist`：允许使用的 MCP 工具。

Skill API：

```text
GET    /skills
POST   /skills
PATCH  /skills/{skill_name}
PATCH  /skills/{skill_name}/enabled
DELETE /skills/{skill_name}

POST   /skills/import/zip
POST   /skills/import/zip/preview
POST   /skills/import/directory
POST   /skills/reload
GET    /skills/tools
GET    /skills/{skill_name}
```

## 会话、上下文和记忆

用户看到的完整聊天历史存放在：

```text
chat_messages
```

Agent 实际看到的上下文由几部分组成：

```text
mem0 长期记忆
+ 当前会话摘要
+ 最近 N 轮原文
+ 当前用户问题
```

相关服务：

```text
backend/services/context_service.py
backend/services/chat_service.py
backend/services/mem0_service.py
```

默认策略：

```text
MEMORY_RECENT_TURNS = 6
MEMORY_COMPRESS_THRESHOLD = 12
MEMORY_TOP_K = 5
```

含义：

- 最近 6 轮保留原文。
- 超过 12 轮开始摘要旧历史。
- 每次最多取 5 条 mem0 长期记忆。

## 监控页面

监控页面仅管理员可见。

监控表：

```text
agent_runs
agent_run_steps
agent_tool_calls
```

默认只记录关键事件：

- Router 分配。
- Worker 开始。
- Worker 完成。
- Worker 异常。
- 工具调用。
- 最终输出。

如果需要保存底层原始事件，可以临时开启：

```powershell
$env:MONITOR_STORE_RAW_EVENTS = "true"
```

监控 API：

```text
GET    /monitor/summary
GET    /monitor/runs
GET    /monitor/runs/{run_id}
DELETE /monitor/runs/{run_id}
```

## 常用命令

前端构建：

```powershell
cd agent-frontend
npm.cmd run build
```

后端语法检查：

```powershell
python -m compileall backend agent rag scripts
```

RAGAS 测评：

```powershell
python scripts/evaluate_rag.py --input eval/rag_robot_eval.jsonl --sync
```

查看 Git 状态：

```powershell
git status --short
```

## 常见问题

### DashScope 模型连不上

如果报错里出现：

```text
WinError 10061
```

通常是程序走了本地代理端口，但代理没有启动，导致连接被拒绝。

处理建议：

- 检查环境变量 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`。
- 确认代理软件是否启动。
- 对国内 DashScope 地址，优先不要强制走本地代理。
- 聊天模型客户端已设置 `trust_env=False`，但某些第三方 embedding/SDK 仍可能读取代理环境。

### HuggingFace 模型或 reranker 加载慢

Reranker 默认配置：

```text
BAAI/bge-reranker-v2-m3
```

建议提前下载本地 snapshot，并在代码中使用本地路径和 `local_files_only=True`，避免服务启动时联网访问 HuggingFace。

### RAG 第一次调用慢

后端启动时会调用 RAG 初始化。若仍然慢，通常是：

- 模型首次加载。
- reranker 首次加载。
- embedding SDK 首次建立连接。
- 向量库首次打开。

可以通过本地缓存模型、减少 rerank、降低 top_k 或预热查询来优化。

### mem0 维度不一致

mem0 的 embedding 维度由模型决定。当前默认：

```text
text-embedding-v4
MEM0_EMBEDDING_DIMS = 1024
```

如果换了 embedding 模型，但复用了旧 Qdrant collection，就可能出现维度不一致。

处理方式：

- 保持 embedding 模型和维度不变。
- 或清空/新建 mem0 collection。
- 或修改 `MEM0_COLLECTION_NAME` 使用新集合。

### 本地 Qdrant 提示 payload index 无效

本地 Qdrant 文件存储会提示：

```text
Payload indexes have no effect in the local Qdrant.
```

这是警告，不影响基本使用。需要 payload index 性能时，改用独立 Qdrant Server。

### 知识库删除后还有旧内容

确认删除流程是否同时删除：

- `knowledge_documents`
- `knowledge_parent_chunks`
- `knowledge_chunks`
- Chroma 向量记录
- 上传文件本体

如果 Chroma 内仍有旧数据，可停止服务后清理 `chroma_db/` 并重新同步。

### RAGAS 分数怎么看

一般判断：

- `faithfulness` 高：回答比较忠实，不容易胡编。
- `context_precision` 高：召回片段噪声少。
- `context_recall` 低：有关键资料没召回。
- `answer_relevancy` 低：回答不够聚焦，可能是模型能力、prompt 或上下文噪声导致。

如果 `context_precision` 和 `faithfulness` 都高，但 `answer_relevancy` 低，优先改回答 prompt，让模型只回答问题直接需要的信息。

### 前端 401

登录态保存在浏览器 localStorage。重新登录或清理：

```text
localStorage.access_token
```

### Skill 修改后没有生效

调用：

```text
POST /skills/reload
```

或在前端 Skill 页面点击重新加载。

## 运行时数据

这些目录会在运行时产生或更新：

```text
datas/chat_multi_history.db
datas/mem0/
chroma_db/
logs/
agent-frontend/dist/
data/uploads/
eval/results/
```

需要重置运行时数据时，先停止后端服务，再清理对应目录。不要在服务运行时直接删除本地 Qdrant、Chroma 或数据库相关文件。

