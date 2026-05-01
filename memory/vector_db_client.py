import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("Engine-VectorDB")

class VectorDBClient:
    def __init__(self, db_path: str = ".chroma_db"): #[cite: 1]
        self.client = chromadb.PersistentClient(path=db_path)
        # 分层索引：1. 里程碑（改变剧情走向的大事） 2. 细节片段（环境、对话）
        self.milestone_col = self.client.get_or_create_collection("milestones")
        self.fragment_col = self.client.get_or_create_collection("fragments")

    def upsert_memory(self, chapter_index: int, content: str, summary: str, is_milestone: bool = False):
        """
        持久化存储记忆。
        如果是里程碑，则双重存储以提高召回权重。
        """
        doc_id = f"ch_{chapter_index}"
        metadata = {"chapter": chapter_index, "type": "milestone" if is_milestone else "fragment"}
        
        if is_milestone:
            # 里程碑存储摘要，便于宏观逻辑检索
            self.milestone_col.add(
                ids=[doc_id],
                documents=[summary],
                metadatas=[metadata]
            )
        
        # 所有内容进入碎片库
        self.fragment_col.add(
            ids=[doc_id],
            documents=[content[:2000]], # 限制长度防止向量偏移
            metadatas=[metadata]
        )
        logger.info(f"✅ 记忆已存档: 第 {chapter_index} 章 ({'里程碑' if is_milestone else '碎片'})")

    def retrieve_context(self, current_query: str, top_k_milestones: int = 2, top_k_fragments: int = 3) -> List[str]:
        """
        多路召回策略：
        1. 召回最近发生的里程碑，确保因果逻辑。
        2. 召回与当前语义相关的细节片段。
        """
        results = []
        
        # 1. 检索里程碑（逻辑链）
        m_results = self.milestone_col.query(
            query_texts=[current_query],
            n_results=top_k_milestones
        )
        for doc in m_results['documents'][0]:
            results.append(f"【关键历史锚点】：{doc}")
            
        # 2. 检索细节碎片（相关性）
        f_results = self.fragment_col.query(
            query_texts=[current_query],
            n_results=top_k_fragments
        )
        for doc in f_results['documents'][0]:
            results.append(f"【相关背景细节】：{doc}")
            
        return results