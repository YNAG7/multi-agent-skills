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

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
