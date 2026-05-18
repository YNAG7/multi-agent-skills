
from backend.db.database import Base, engine

# 关键：必须导入 models，SQLAlchemy 才知道有哪些表
from backend.models import User, ChatSession, ChatMessage, UserMemory


def init_db():
    Base.metadata.create_all(bind=engine)