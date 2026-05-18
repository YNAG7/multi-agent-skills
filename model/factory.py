import os
from abc import ABC, abstractmethod
from typing import Optional

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
# 【核心修改 1】：引入 ChatOpenAI
from langchain_openai import ChatOpenAI 
from langchain_community.embeddings import DashScopeEmbeddings
from utils.config_handler import rag_conf

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings|BaseChatModel]:
        pass
    
class SmartChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings|BaseChatModel]:
        # 【核心修改 2】：使用 ChatOpenAI 调用阿里云模型
        return ChatOpenAI(
            api_key=os.environ.get("DASHSCOPE_API_KEY"), # 请确保环境变量中配置了你的 Key
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", # 阿里云的 OpenAI 兼容网关
            model=rag_conf['smart_chat_model_name'],
            streaming=True
        )
    
class CheapChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings|BaseChatModel]:
        return ChatOpenAI(
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=rag_conf['cheap_chat_model_name'],
            streaming=True
        )
    
class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings|BaseChatModel]:
        # 嵌入模型 (Embedding) 不涉及流式输出和工具调用，
        # 继续使用原生的 DashScopeEmbeddings 是最稳定且性能最好的选择。
        return DashScopeEmbeddings(model=rag_conf['embedding_model_name'])
    
smart_chat_model = SmartChatModelFactory().generator()
cheap_chat_model = CheapChatModelFactory().generator()
embedding_model = EmbeddingModelFactory().generator()