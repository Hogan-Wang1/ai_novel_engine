import logging
from typing import List, Dict, Any, Optional

try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger("Engine-CoPilot.VectorDB")

class VectorDBClient:
    """
    冷记忆向量数据库终端。
    专用于存储和检索前情提要、历史伏笔与环境设定。
    """
    def __init__(self, db_path: str = "./.chroma_db", collection_name: str = "novel_cold_memory"):
        if chromadb is None:
            logger.critical("🛑 缺少冷记忆核心组件！请立即在终端运行: pip install chromadb")
            raise ImportError("Missing required package: chromadb")

        self.db_path = db_path
        
        try:
            # 采用 PersistentClient 实现本地持久化，断电重启记忆不丢失
            self.client = chromadb.PersistentClient(path=self.db_path)
            
            # 获取或创建集合，使用余弦相似度进行文本匹配
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"} 
            )
            logger.info(f"🧠 冷记忆向量矩阵挂载成功 | 路径: {self.db_path} | 集合: {collection_name}")
        except Exception as e:
            logger.critical(f"🛑 向量数据库初始化彻底失败: {str(e)}")
            raise e

    def add_memory(self, memory_id: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        """
        将剧情摘要或重要设定写入冷记忆矩阵
        """
        try:
            self.collection.add(
                documents=[text],
                metadatas=[metadata or {}],
                ids=[memory_id]
            )
            logger.debug(f"💾 冷记忆碎片已封存: [{memory_id}]")
        except Exception as e:
            logger.error(f"❌ 写入冷记忆失败 (ID: {memory_id}): {str(e)}")

    def search_relevant_lore(self, query: str, top_k: int = 2) -> str:
        """
        检索与当前上下文最相关的历史记忆。
        包含熔断降级策略：如果报错，返回友好提示而非抛出异常中断流水线。
        """
        if not query.strip():
            return "无明确查询条件。"

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            # ChromaDB 的 documents 返回的是二维列表
            if not results['documents'] or not results['documents'][0]:
                return "未检索到相关的历史记忆。"
                
            retrieved_texts = results['documents'][0]
            
            # 将检索到的片段拼接为结构化文本
            context_str = "\n".join([f" - {text}" for text in retrieved_texts])
            return context_str
            
        except Exception as e:
            logger.error(f"❌ 检索冷记忆时发生局部异常: {str(e)}")
            return "记忆检索系统暂时波动，未获取到历史上下文。"