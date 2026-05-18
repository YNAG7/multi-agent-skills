import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from rag.vector_store import VectorStoreService
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from utils.logger_handler import logger
from utils.config_handler import chroma_conf,rag_conf
from langchain_classic.retrievers import EnsembleRetriever,ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker

from langchain_community.cross_encoders import HuggingFaceCrossEncoder


class RagSummarizeService(object):
    def __init__(self):
        self.vector_store=VectorStoreService()
        self.vector_retriever=self.vector_store.get_retriever()
        
        self.bm25_retriever=self.__init_bm25_retriever()
        if self.bm25_retriever:
            self.ensemble_retriever=EnsembleRetriever(
                retrievers=[self.vector_retriever, self.bm25_retriever],
                weights=[0.6, 0.4] # 可以根据需要调整权重
            )
        else:
            self.ensemble_retriever=self.vector_retriever
        
        compressor=CrossEncoderReranker(model=HuggingFaceCrossEncoder(model_name=rag_conf['reranker_model_name']),top_n=chroma_conf['top_n'])
        
        self.retriever=ContextualCompressionRetriever(
            base_retriever=self.ensemble_retriever,
            base_compressor=compressor
        ) 
        
    def __init_bm25_retriever(self):
        try:
            db_data=self.vector_store.vector_store.get()
            texts=db_data.get("documents", [])
            metadata=db_data.get("metadatas", [])
            if not texts:
                return None
            
            bm25=BM25Retriever.from_texts(texts=texts, metadatas=metadata)
            bm25.k=chroma_conf['k']
            logger.info(f"[RAG 服务] BM25 内存索引构建成功，共加载 {len(texts)} 个文本块。")
            return bm25
        except Exception as e:
            logger.error(f"[RAG 服务] 构建 BM25 失败: {e}")
            return None

    def _init_chain(self):
        chain=self.prompt_template | self.model |StrOutputParser()
        return chain
    
    def retriever_docs(self, query:str)->list[Document]:
        return self.retriever.invoke(query)
    
    def rag_summarize(self, query: str) -> str:
    
        context_docs = self.retriever_docs(query)
    
        if not context_docs:
            return "未从知识库中检索到相关资料。"
        
        context = "以下是从知识库中检索到的最相关的原始资料段落：\n\n"
    
        for counter, doc in enumerate(context_docs, 1):
            # 直接把内容和元数据用纯文本拼装，大模型最喜欢读这种干净的结构
            context += f"【参考资料 {counter}】\n"
            context += f"内容: {doc.page_content}\n"
            context += f"元数据: {doc.metadata}\n"
            context += "-" * 30 + "\n"
        
        return context
