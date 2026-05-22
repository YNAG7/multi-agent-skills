# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth_api import router as auth_router
from backend.api.chat_api import router as chat_router
from backend.api.knowledge_api import router as knowledge_router
from backend.api.monitor_api import router as monitor_router
from backend.api.skill_api import router as skill_router
from backend.api.user_api import router as user_router
from backend.core.config import settings
from backend.db.init_db import init_db
from utils.logger_handler import logger

# 新增：导入 agent_service
from backend.services.agent_service import agent_service


app = FastAPI(
    title="Multi-Agent Platform API",
    description="基于 FastAPI + LangGraph + Skills 的 Agent 后端",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    """
    FastAPI 启动时执行：

    1. 初始化数据库
    2. 初始化 Agent Graph
       - 读取 skills
       - 注入远端 MCP tools
       - 构建 LangGraph
       - 创建 ToolNode
    """
    init_db()

    try:
        from agent.tools.common_tools import initialize_rag

        initialize_rag()
    except Exception as e:
        logger.error(f"[Startup] RAG warmup failed: {e}")

    await agent_service.init()


@app.on_event("shutdown")
async def on_shutdown():
    """
    FastAPI 关闭时释放资源。
    """
    await agent_service.close()


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


app.include_router(
    auth_router,
    prefix="/auth",
    tags=["Auth"],
)

app.include_router(
    user_router,
    prefix="/users",
    tags=["User"],
)

app.include_router(
    chat_router,
    prefix="/chat",
    tags=["Chat"],
)

app.include_router(
    skill_router,
    prefix="/skills",
    tags=["Skill"],
)

app.include_router(
    knowledge_router,
    prefix="/knowledge",
    tags=["Knowledge"],
)

app.include_router(
    monitor_router,
    prefix="/monitor",
    tags=["Monitor"],
)
