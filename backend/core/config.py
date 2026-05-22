import os


class Settings:
    # PostgreSQL
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "root")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "127.0.0.1")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "agent")

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "SsMswbikNNYZh68BlwJBONixaSywmZcL4zV8uO5Uh1nBd8gs-MUL9kvt8qYyQt4qG0vWbw276j2_9RdPiB6eGA")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Memory
    MEMORY_ENABLED: bool = os.getenv("MEMORY_ENABLED", "true").lower() == "true"
    MEMORY_RECENT_TURNS: int = int(os.getenv("MEMORY_RECENT_TURNS", "6"))
    MEMORY_COMPRESS_THRESHOLD: int = int(os.getenv("MEMORY_COMPRESS_THRESHOLD", "12"))
    MEMORY_TOP_K: int = int(os.getenv("MEMORY_TOP_K", "5"))
    MEM0_DIR: str = os.getenv("MEM0_DIR", "datas/mem0")
    MEM0_LLM_PROVIDER: str = os.getenv("MEM0_LLM_PROVIDER", "openai")
    MEM0_LLM_MODEL: str = os.getenv("MEM0_LLM_MODEL", "qwen-turbo")
    MEM0_LLM_BASE_URL: str = os.getenv(
        "MEM0_LLM_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    MEM0_LLM_API_KEY: str | None = os.getenv("MEM0_LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    MEM0_EMBEDDER_PROVIDER: str = os.getenv("MEM0_EMBEDDER_PROVIDER", "openai")
    MEM0_EMBEDDER_MODEL: str = os.getenv("MEM0_EMBEDDER_MODEL", "text-embedding-v4")
    MEM0_EMBEDDER_BASE_URL: str = os.getenv(
        "MEM0_EMBEDDER_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    MEM0_EMBEDDER_API_KEY: str | None = os.getenv("MEM0_EMBEDDER_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    MEM0_COLLECTION_NAME: str = os.getenv("MEM0_COLLECTION_NAME", "mem0")
    MEM0_EMBEDDING_DIMS: int = int(os.getenv("MEM0_EMBEDDING_DIMS", "1024"))

    # Monitor
    MONITOR_STORE_RAW_EVENTS: bool = os.getenv("MONITOR_STORE_RAW_EVENTS", "false").lower() == "true"
    MONITOR_CAPTURE_OBSERVED_TOOLS: bool = os.getenv("MONITOR_CAPTURE_OBSERVED_TOOLS", "true").lower() == "true"

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    ADMIN_USERNAMES: set[str] = {
        item.strip()
        for item in os.getenv("ADMIN_USERNAMES", "admin").split(",")
        if item.strip()
    }

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
