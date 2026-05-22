from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from langchain_chroma import Chroma
from langchain_core.documents import Document
from sqlalchemy.orm import Session

from backend.db.database import SessionLocal
from backend.models import KnowledgeChunk, KnowledgeDocument, KnowledgeParentChunk
from model.factory import embedding_model
from rag.chunker import build_parent_child_chunks
from rag.document_parser import parse_document
from utils.config_handler import chroma_conf
from utils.logger_handler import logger
from utils.path_tool import get_abs_path

# 限制单个用户上传文件的最大体积（当前设置为 50MB
MAX_UPLOAD_SIZE = 50 * 1024 * 1024

# 获取当前系统时间的工具函数
def _now() -> datetime:
    return datetime.now()

# 强力清洗并过滤文件名，防止特殊字符或路径穿越攻击（Path Traversal），限制主文件名最长 80 字符
def _safe_filename(name: str) -> str:
    stem = Path(name or "knowledge").stem.strip() or "knowledge"
    suffix = Path(name or "").suffix.lower()
    stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", stem).strip(".-_")
    stem = stem[:80] or "knowledge"
    return f"{stem}{suffix}"

# 以流式分块（每次 1MB）方式读取磁盘文件并计算其 SHA-256 摘要，用于精准比对内容去重
def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

# 编码并计算纯文本字符串的 SHA-256 摘要，用于生成分片唯一的哈希指纹
def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# 将元数据字典序列化为 JSON 字符串，强制关闭 ASCII 编码以完美支持中文，并对键名排序以保持哈希一致性
def _metadata_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)

# 安全反序列化数据库中的 JSON 元数据字符串，发生任何异常时优雅返回空字典
def _load_metadata(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

# 安全校验子路径（child）是否严格包含在父根目录（parent）内，用以规避非法的恶意相对路径
def _is_inside(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


class VectorStoreService:
    """
    DB-backed knowledge index with Chroma as the vector backend.

    The database owns document/chunk state. Chroma stores embeddings keyed by the
    stable chunk vector_id, so file updates and deletes can remove stale vectors
    deterministically.
    """
    # 初始化服务，绑定 Chroma 向量后端，并从全局配置中加载父子切块（Parent-Child）双层视窗的各项核心参数
    def __init__(self):
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embedding_model,
            persist_directory=chroma_conf["persist_directory"],
        )
        self.parent_chunk_size = int(chroma_conf.get("parent_chunk_size", 1200))
        self.parent_chunk_overlap = int(chroma_conf.get("parent_chunk_overlap", 120))
        self.child_chunk_size = int(chroma_conf.get("child_chunk_size", 360))
        self.child_chunk_overlap = int(chroma_conf.get("child_chunk_overlap", 80))
        self.data_root = Path(get_abs_path(chroma_conf.get("data_path", "data"))).resolve()
        self.upload_root = Path(get_abs_path(chroma_conf.get("upload_path", "data/uploads"))).resolve()
        self.allowed_extensions = {
            f".{item.lower().lstrip('.')}"
            for item in chroma_conf.get("allow_knowledge_file_type", ["txt", "pdf"])
        }
    # 获取原生向量库检索器，指定召回的相似子分片（Child Chunks）数量 k
    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})
    
    # 标准文档加载入口，底层直接路由至磁盘目录双向同步流水线
    def load_documents(self) -> dict[str, int]:
        return self.sync_data_directory()
    
    # 数据目录双向对齐核心：正向遍历同步磁盘新老文件，反向盘点物理抹除已被用户人肉删除的死记录
    def sync_data_directory(self) -> dict[str, int]:
        self.data_root.mkdir(parents=True, exist_ok=True)
        files = self._scan_files()
        seen_paths = {self._storage_path(path) for path in files}
        stats = {
            "scanned": len(files),
            "indexed": 0,
            "skipped": 0,
            "deleted": 0,
            "failed": 0,
        }

        with SessionLocal() as db:
            for path in files:
                result = self.index_file(db, path, source="data")
                stats[result] = stats.get(result, 0) + 1

            for document in db.query(KnowledgeDocument).all():
                document_path = self._path_from_storage(document.path)
                if not _is_inside(self.data_root, document_path):
                    continue
                if document.path in seen_paths:
                    continue

                self.delete_document(db, document.id, remove_file=False)
                stats["deleted"] += 1

        logger.info(
            "[RAG] knowledge sync done: scanned=%s indexed=%s skipped=%s deleted=%s failed=%s",
            stats["scanned"],
            stats["indexed"],
            stats["skipped"],
            stats["deleted"],
            stats["failed"],
        )
        return stats
    
    # 异步接收前端文件上传流，限流限额落盘到 uploads 隔离区，清洗文件名并强行触发覆盖率索引
    async def save_upload(
        self,
        db: Session,
        file: UploadFile,
        uploaded_by: int | None = None,
    ) -> KnowledgeDocument:
        filename = _safe_filename(file.filename or "knowledge")
        suffix = Path(filename).suffix.lower()
        if suffix not in self.allowed_extensions:
            allowed = ", ".join(sorted(self.allowed_extensions))
            raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed}")

        self.upload_root.mkdir(parents=True, exist_ok=True)
        target = self._unique_upload_path(filename)
        total = 0

        with target.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_SIZE:
                    out.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="File is too large")
                out.write(chunk)

        result = self.index_file(
            db,
            target,
            source="upload",
            uploaded_by=uploaded_by,
            content_type=file.content_type,
            force=True,
        )
        if result == "failed":
            document = self.get_document_by_path(db, target)
            detail = document.error if document and document.error else "Indexing failed"
            raise HTTPException(status_code=500, detail=detail)

        document = self.get_document_by_path(db, target)
        if document is None:
            raise HTTPException(status_code=500, detail="Knowledge document was not created")
        return document
    
    # 单个文件解析入库核心状态机：执行两层排重拦截（元数据/内容哈希），锁定行级事务所有权（pending/indexing），防止高并发多线程撞车
    def index_file(
        self,
        db: Session,
        path: str | Path,
        source: str = "data",
        uploaded_by: int | None = None,
        content_type: str | None = None,
        force: bool = False,
    ) -> str:
        file_path = Path(path).resolve()
        storage_path = self._storage_path(file_path)
        suffix = file_path.suffix.lower()

        if suffix not in self.allowed_extensions:
            return "skipped"

        if not file_path.exists() or not file_path.is_file():
            return "skipped"

        stat = file_path.stat()
        document = self.get_document_by_path(db, file_path)
        if (
            document
            and not force
            and document.mtime == stat.st_mtime
            and document.size_bytes == stat.st_size
            and document.status == "indexed"
        ):
            return "skipped"

        content_hash = _sha256_file(file_path)
        if (
            document
            and not force
            and document.content_hash == content_hash
            and document.status == "indexed"
        ):
            document.mtime = stat.st_mtime
            document.size_bytes = stat.st_size
            document.updated_at = _now()
            db.commit()
            return "skipped"

        if document is None:
            document = KnowledgeDocument(
                path=storage_path,
                filename=file_path.name,
                source=source,
                content_type=content_type or mimetypes.guess_type(file_path.name)[0],
                size_bytes=stat.st_size,
                mtime=stat.st_mtime,
                content_hash=content_hash,
                status="pending",
                uploaded_by=uploaded_by,
            )
            db.add(document)
            db.commit()
            db.refresh(document)
        else:
            document.filename = file_path.name
            document.source = document.source or source
            document.content_type = content_type or document.content_type or mimetypes.guess_type(file_path.name)[0]
            document.size_bytes = stat.st_size
            document.mtime = stat.st_mtime
            document.content_hash = content_hash
            document.status = "indexing"
            document.error = None
            document.updated_at = _now()
            if uploaded_by is not None:
                document.uploaded_by = uploaded_by
            db.commit()
            db.refresh(document)

        try:
            split_documents = self._split_file(file_path)
            chunk_count = self._replace_chunks(db, document, split_documents)

            document.status = "indexed"
            document.chunk_count = chunk_count
            document.error = None
            document.indexed_at = _now()
            document.updated_at = _now()
            db.commit()
            return "indexed"
        except Exception as e:
            logger.error(f"[RAG] failed to index {file_path}: {e}", exc_info=True)
            document.status = "failed"
            document.error = str(e)
            document.updated_at = _now()
            db.commit()
            return "failed"

    # 文档物理抹除：定点清除 Chroma 向量库关联向量，联动清空关系库的父子切块及主文档记录，可选择性同步剔除磁盘实体物理文件
    def delete_document(
        self,
        db: Session,
        document_id: int,
        remove_file: bool = False,
    ) -> bool:
        document = db.get(KnowledgeDocument, document_id)
        if document is None:
            return False

        chunks = (
            db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.document_id == document_id)
            .all()
        )
        vector_ids = [chunk.vector_id for chunk in chunks]
        self._delete_vectors(vector_ids)

        if remove_file:
            file_path = self._resolve_storage_path(document.path)
            roots = [self.data_root, self.upload_root]
            if file_path and any(_is_inside(root, file_path) for root in roots):
                file_path.unlink(missing_ok=True)

        db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document_id).delete(
            synchronize_session=False
        )
        db.query(KnowledgeParentChunk).filter(KnowledgeParentChunk.document_id == document_id).delete(
            synchronize_session=False
        )
        db.delete(document)
        db.commit()
        return True

    # 手动触发指定文档强制重新索引（无脑绕过排重缓存防线）
    def reindex_document(self, db: Session, document_id: int) -> KnowledgeDocument | None:
        document = db.get(KnowledgeDocument, document_id)
        if document is None:
            return None

        file_path = self._resolve_storage_path(document.path)
        if file_path is None:
            document.status = "failed"
            document.error = "Knowledge file path is invalid"
            db.commit()
            db.refresh(document)
            return document

        self.index_file(db, file_path, source=document.source, uploaded_by=document.uploaded_by, force=True)
        db.refresh(document)
        return document

    # 查询系统存量的所有知识库主文档记录，按更新时间及物理 ID 倒序排列
    def list_documents(self, db: Session) -> list[KnowledgeDocument]:
        return (
            db.query(KnowledgeDocument)
            .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())
            .all()
        )

    # 全量加载所有状态正常（indexed）的子切块实体，主要用于上层应用动态重构内存倒排索引
    def list_chunks(self, db: Session) -> list[KnowledgeChunk]:
        return (
            db.query(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .filter(KnowledgeDocument.status == "indexed")
            .order_by(KnowledgeChunk.document_id.asc(), KnowledgeChunk.chunk_index.asc())
            .all()
        )

    # 根据清洗规范化后的标准路径，精确从关系库捞取对应的文档主表记录
    def get_document_by_path(self, db: Session, path: str | Path) -> KnowledgeDocument | None:
        return (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.path == self._storage_path(Path(path).resolve()))
            .first()
        )

    # 导出完整的子切块文本对象列表，专门供 RagSummarizeService 在启动时就地构建高性能本地内存 BM25 稀疏关键词检索树
    def db_documents_for_bm25(self) -> list[Document]:
        with SessionLocal() as db:
            chunks = self.list_chunks(db)
            return [
                Document(
                    page_content=chunk.text,
                    metadata=_load_metadata(chunk.metadata_json),
                )
                for chunk in chunks
            ]

    # 递归正向扫描本地 data_root 目录下的所有物理实体文件，强力核对并筛选合法后缀白名单列表
    def _scan_files(self) -> list[Path]:
        if not self.data_root.exists():
            return []

        result: list[Path] = []
        for item in self.data_root.rglob("*"):
            if not item.is_file():
                continue
            if item.suffix.lower() not in self.allowed_extensions:
                continue
            result.append(item.resolve())
        return result

    # 离线级切片路由器：先调自适应解析器剥离脱水噪音，再调 build_parent_child_chunks 将纯文本当场重构成双层主从层级树
    def _split_file(self, path: Path) -> list[Document]:
        documents = parse_document(path)
        if not documents:
            raise ValueError("No readable text content found")

        parent_chunks = build_parent_child_chunks(
            documents,
            parent_size=self.parent_chunk_size,
            parent_overlap=self.parent_chunk_overlap,
            child_size=self.child_chunk_size,
            child_overlap=self.child_chunk_overlap,
        )
        if not parent_chunks:
            raise ValueError("No valid chunks after splitting")

        return parent_chunks

    # 双库分离持久化施工核心（具备绝对幂等性）：全量物理扫除历史残渣，父块完整长文进关系库刷出自增 ID，子块小片段绑定父 ID 灌入关系库，并微量分批（batch）推送向量库 Chroma
    def _replace_chunks(
        self,
        db: Session,
        document: KnowledgeDocument,
        parent_chunks,
    ) -> int:
        old_chunks = (
            db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.document_id == document.id)
            .all()
        )
        self._delete_vectors([chunk.vector_id for chunk in old_chunks])
        db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete(
            synchronize_session=False
        )
        db.query(KnowledgeParentChunk).filter(KnowledgeParentChunk.document_id == document.id).delete(
            synchronize_session=False
        )
        db.flush()

        vector_docs: list[Document] = []
        vector_ids: list[str] = []
        child_counter = 0

        for parent_index, parent_chunk in enumerate(parent_chunks):
            parent_text = parent_chunk.text.strip()
            if not parent_text:
                continue

            parent_hash = _sha256_text(parent_text)
            parent_metadata = {
                **(parent_chunk.metadata or {}),
                "document_id": document.id,
                "parent_index": parent_index,
                "parent_hash": parent_hash,
                "source": document.path,
                "filename": document.filename,
            }
            parent_record = KnowledgeParentChunk(
                document_id=document.id,
                parent_index=parent_index,
                parent_hash=parent_hash,
                text=parent_text,
                metadata_json=_metadata_json(parent_metadata),
            )
            db.add(parent_record)
            db.flush()

            for child_chunk in parent_chunk.children:
                text = child_chunk.text.strip()
                if not text:
                    continue

                chunk_hash = _sha256_text(text)
                vector_id = f"knowledge-{document.id}-{child_counter}-{chunk_hash[:12]}"
                metadata = {
                    **(child_chunk.metadata or {}),
                    "document_id": document.id,
                    "parent_id": parent_record.id,
                    "parent_index": parent_index,
                    "parent_hash": parent_hash,
                    "chunk_index": child_counter,
                    "chunk_hash": chunk_hash,
                    "source": document.path,
                    "filename": document.filename,
                }

                db.add(
                    KnowledgeChunk(
                        document_id=document.id,
                        parent_id=parent_record.id,
                        chunk_index=child_counter,
                        chunk_hash=chunk_hash,
                        vector_id=vector_id,
                        text=text,
                        metadata_json=_metadata_json(metadata),
                    )
                )
                vector_ids.append(vector_id)
                vector_docs.append(Document(page_content=text, metadata=metadata))
                child_counter += 1

        if not vector_docs:
            raise ValueError("No non-empty chunks after splitting")

        batch_size = int(chroma_conf.get("embedding_batch_size", 10))
        for start in range(0, len(vector_docs), batch_size):
            end = start + batch_size
            self.vector_store.add_documents(
                vector_docs[start:end],
                ids=vector_ids[start:end],
            )

        return len(vector_docs)

    # 逆向父块语义放大器：接收前台检索命中打分极高的子块小盒子列表，抓取 metadata 中的 parent_id 执行高效库级 IN 查询，完成“小块匹配、大块替换”，并执行严密的全局去重，防止大模型上下文爆量与重复阅读
    def expand_to_parent_documents(self, docs: list[Document]) -> list[Document]:
        parent_ids: list[int] = []
        for doc in docs:
            parent_id = doc.metadata.get("parent_id")
            if isinstance(parent_id, int) and parent_id not in parent_ids:
                parent_ids.append(parent_id)

        if not parent_ids:
            return docs

        with SessionLocal() as db:
            parents = (
                db.query(KnowledgeParentChunk)
                .filter(KnowledgeParentChunk.id.in_(parent_ids))
                .all()
            )
            by_id = {parent.id: parent for parent in parents}

        result: list[Document] = []
        seen: set[int] = set()
        for doc in docs:
            parent_id = doc.metadata.get("parent_id")
            if not isinstance(parent_id, int) or parent_id in seen:
                continue

            parent = by_id.get(parent_id)
            if parent is None:
                result.append(doc)
                continue

            metadata = _load_metadata(parent.metadata_json)
            metadata["matched_child"] = {
                "chunk_index": doc.metadata.get("chunk_index"),
                "chunk_hash": doc.metadata.get("chunk_hash"),
            }
            result.append(Document(page_content=parent.text, metadata=metadata))
            seen.add(parent_id)

        return result or docs

    # 底层向量定点物理爆破：安全封装 Chroma 的物理删除 API，静默拦截并降级捕捉任何未知的库级驱动报错
    def _delete_vectors(self, vector_ids: list[str]) -> None:
        if not vector_ids:
            return

        try:
            self.vector_store.delete(ids=vector_ids)
        except Exception as e:
            logger.warning(f"[RAG] vector delete skipped: {e}")

    # 重名安全自动软增量递增：若物理上传路径已存在同名冲突，通过正向循环在文件名后置自动盲加计数后缀（-1, -2），上限 10000 次拦截，严防重写覆盖
    def _unique_upload_path(self, filename: str) -> Path:
        target = self.upload_root / filename
        if not target.exists():
            return target

        stem = target.stem
        suffix = target.suffix
        for index in range(1, 10000):
            candidate = self.upload_root / f"{stem}-{index}{suffix}"
            if not candidate.exists():
                return candidate

        raise HTTPException(status_code=409, detail="Too many files with the same name")

    def _storage_path(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return str(resolved.relative_to(Path(get_abs_path(".")).resolve())).replace("\\", "/")
        except ValueError:
            return str(resolved).replace("\\", "/")

    def _path_from_storage(self, storage_path: str) -> Path:
        path = Path(storage_path)
        if not path.is_absolute():
            path = Path(get_abs_path(storage_path))
        return path.resolve()

    def _resolve_storage_path(self, storage_path: str) -> Path | None:
        resolved = self._path_from_storage(storage_path)
        if resolved.exists():
            return resolved
        return None


