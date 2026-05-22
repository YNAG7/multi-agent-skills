import os
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_openai import ChatOpenAI

from utils.config_handler import rag_conf


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


def _dashscope_chat_model(model_name: str) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model=model_name,
        streaming=True,
        http_client=httpx.Client(trust_env=False),
        http_async_client=httpx.AsyncClient(trust_env=False),
    )


class SmartChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return _dashscope_chat_model(rag_conf["smart_chat_model_name"])


class CheapChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return _dashscope_chat_model(rag_conf["cheap_chat_model_name"])


class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return DashScopeEmbeddings(model=rag_conf["embedding_model_name"])


smart_chat_model = SmartChatModelFactory().generator()
cheap_chat_model = CheapChatModelFactory().generator()
embedding_model = EmbeddingModelFactory().generator()
