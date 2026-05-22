from __future__ import annotations

import os
from pathlib import Path

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from langchain_classic.retrievers import ContextualCompressionRetriever, EnsembleRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from rag.vector_store import VectorStoreService
from utils.config_handler import chroma_conf, rag_conf
from utils.logger_handler import logger


class RagSummarizeService(object):
    def __init__(self, sync_on_init: bool = True):
        self.vector_store = VectorStoreService()
        if sync_on_init:
            self.vector_store.sync_data_directory()
        self.refresh_retrievers()

    def refresh_retrievers(self, reload_vector_store: bool = False) -> None:
        if reload_vector_store:
            self.vector_store = VectorStoreService()

        self.vector_retriever = self.vector_store.get_retriever()
        self.bm25_retriever = self.__init_bm25_retriever()
        if self.bm25_retriever:
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[self.vector_retriever, self.bm25_retriever],
                weights=[0.6, 0.4],
            )
        else:
            self.ensemble_retriever = self.vector_retriever

        self.retriever = self.__init_rerank_retriever()

    def sync_and_refresh(self) -> dict[str, int]:
        stats = self.vector_store.sync_data_directory()
        self.refresh_retrievers()
        return stats

    def __resolve_local_hf_model(self, model_name: str) -> str:
        model_path = Path(model_name)
        if model_path.exists():
            return str(model_path)

        cache_root = Path(
            os.environ.get("HF_HUB_CACHE")
            or os.environ.get("HUGGINGFACE_HUB_CACHE")
            or Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
        )
        repo_cache = cache_root / f"models--{model_name.replace('/', '--')}"
        refs_main = repo_cache / "refs" / "main"
        if refs_main.exists():
            revision = refs_main.read_text(encoding="utf-8").strip()
            snapshot = repo_cache / "snapshots" / revision
            if snapshot.exists():
                logger.info(f"[RAG] using local reranker cache: {snapshot}")
                return str(snapshot)

        return model_name

    def __init_rerank_retriever(self):
        try:
            reranker_model_name = self.__resolve_local_hf_model(rag_conf["reranker_model_name"])
            reranker_model = HuggingFaceCrossEncoder(
                model_name=reranker_model_name,
                model_kwargs={"local_files_only": Path(reranker_model_name).exists()},
            )
            compressor = CrossEncoderReranker(model=reranker_model, top_n=chroma_conf["top_n"])

            return ContextualCompressionRetriever(
                base_retriever=self.ensemble_retriever,
                base_compressor=compressor,
            )
        except Exception as e:
            logger.warning(f"[RAG] reranker initialization failed, fallback to vector/BM25: {e}")
            return self.ensemble_retriever

    def __init_bm25_retriever(self):
        try:
            docs = self.vector_store.db_documents_for_bm25()
            if not docs:
                return None

            bm25 = BM25Retriever.from_documents(docs)
            bm25.k = chroma_conf["k"]
            logger.info(f"[RAG] BM25 built from knowledge_chunks, chunks={len(docs)}")
            return bm25
        except Exception as e:
            logger.error(f"[RAG] failed to build BM25: {e}")
            return None

    def retriever_docs(self, query: str) -> list[Document]:
        try:
            docs = self.retriever.invoke(query)
        except Exception as e:
            if self.bm25_retriever:
                logger.warning(f"[RAG] primary retrieval failed, fallback to BM25: {e}")
                docs = self.bm25_retriever.invoke(query)
            else:
                raise
        return self.vector_store.expand_to_parent_documents(docs)

    def warmup(self) -> None:
        docs = self.retriever_docs("知识库初始化")
        logger.info(f"[RAG] warmup done, retrieved chunks={len(docs)}")

    def rag_summarize(self, query: str) -> str:
        context_docs = self.retriever_docs(query)

        if not context_docs:
            return "未从知识库中检索到相关资料。"

        context = "以下是从知识库中检索到的最相关原始资料片段：\n\n"

        for counter, doc in enumerate(context_docs, 1):
            context += f"【参考资料 {counter}】\n"
            context += f"内容: {doc.page_content}\n"
            context += f"元数据: {doc.metadata}\n"
            context += "-" * 30 + "\n"

        return context
