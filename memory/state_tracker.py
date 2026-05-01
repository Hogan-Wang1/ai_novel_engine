import os
import json
import chromadb
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from loguru import logger

# ==========================================
# 状态机定义：角色与世界的绝对真理
# ==========================================
class CharacterState(BaseModel):
    """角色的绝对状态锁，每次章节更新后由模型抽取并强制覆盖"""
    name: str
    is_alive: bool = Field(True, description="生死状态，一旦为False，后续大纲严禁包含其活跃剧情")
    current_location: str = Field(..., description="当前所处位置的精确描述")
    power_level_current: str = Field(..., description="当前真实战力状态（包含受伤/透支等debuff）")
    inventory: List[str] = Field(default_factory=list, description="当前身上携带的重要道具/法宝清单")

class WorldState(BaseModel):
    """世界时间线与全局摘要"""
    current_chapter_index: int = 0
    timeline: str = Field(..., description="小说当前的绝对时间节点（如：深渊纪元304年，凛冬）")
    rolling_summary: str = Field(
        default="", 
        description="最近5万字剧情的极度浓缩摘要，必须包含因果关系，严禁超过800字"
    )
    active_characters: Dict[str, CharacterState] = Field(default_factory=dict)

# ==========================================
# 记忆管理器：向量 RAG + 状态机维护
# ==========================================
class MemoryManager:
    def __init__(self):
        # 1. 初始化本地向量数据库 (持久化)
        db_path = os.getenv("VECTOR_DB_PERSIST_DIR", "./data/chroma_db")
        os.makedirs(db_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        
        # 创建或加载小说专属集合
        self.lore_collection = self.chroma_client.get_or_create_collection(
            name="narrative_lore",
            metadata={"hnsw:space": "cosine"}
        )
        
        # 2. 初始化世界状态机
        self.state_file_path = "./data/world_state.json"
        self.world_state = self._load_or_init_state()

    def _load_or_init_state(self) -> WorldState:
        """从磁盘加载最新的世界状态，防止程序意外中断后重启丢失进度"""
        if os.path.exists(self.state_file_path):
            try:
                with open(self.state_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info("成功从磁盘唤醒 WorldState 状态机。")
                    return WorldState(**data)
            except Exception as e:
                logger.error(f"加载状态机失败: {e}，将初始化全新状态。")
        
        logger.warning("未检测到历史状态，初始化全新 WorldState。")
        return WorldState(timeline="初始纪元")

    def save_state(self):
        """将当前状态机硬写入磁盘，此动作在每章生成完毕后触发"""
        os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
        with open(self.state_file_path, "w", encoding="utf-8") as f:
            f.write(self.world_state.model_dump_json(indent=4))
        logger.debug(f"第 {self.world_state.current_chapter_index} 章状态机已落盘保存。")

    # ==========================================
    # 长期记忆 (RAG) 写入与检索
    # ==========================================
    def archive_chapter_to_lore(self, chapter_index: int, chapter_summary: str, key_events: List[str]):
        """
        将旧章节的核心事件写入向量数据库，供未来遥远的章节检索。
        :param chapter_summary: 本章内容的完整摘要
        :param key_events: 抽取的原子化事件库（例如："林动在炎城获得了祖石"）
        """
        # 将原子事件作为独立 document 存入，提高检索命中率
        documents = [chapter_summary] + key_events
        ids = [f"chap_{chapter_index}_sum"] + [f"chap_{chapter_index}_event_{i}" for i in range(len(key_events))]
        metadatas = [{"chapter": chapter_index, "type": "summary"}] + [{"chapter": chapter_index, "type": "event"} for _ in key_events]
        
        self.lore_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"第 {chapter_index} 章记忆碎片已归档至 ChromaDB。")

    def recall_lore(self, query: str, n_results: int = 3) -> str:
        """
        通过大纲或用户的暗示，检索历史伏笔。
        例如 query = "主角上次使用火属性法宝的场景"
        """
        results = self.lore_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        if not results['documents'] or not results['documents'][0]:
            return "记忆库中未找到相关历史记录。"
            
        retrieved_texts = results['documents'][0]
        logger.debug(f"记忆检索触发，召回了 {len(retrieved_texts)} 条历史碎片。")
        return "\n".join([f"- {text}" for text in retrieved_texts])

    # ==========================================
    # 供给下游生成流的上下文拼接器
    # ==========================================
    def get_context_payload_for_next_chapter(self) -> str:
        """
        组装发给大模型的系统级上下文，这是零人工干预下大模型唯一的“眼睛”。
        """
        state = self.world_state
        payload = f"""
[CRITICAL CONTEXT - ABSOLUTE TRUTH]
当前章节进度: 第 {state.current_chapter_index + 1} 章
当前时间线: {state.timeline}

【近期剧情滚动摘要】
{state.rolling_summary if state.rolling_summary else "剧情刚刚开始，无前情提要。"}

【核心活跃角色当前状态】 (严禁在生成中违背以下状态：死人不能说话，没带的法宝不能用)
"""
        for char_name, char_data in state.active_characters.items():
            payload += f"- {char_name}: [位置]{char_data.current_location} | [状态]{char_data.power_level_current} | [持有物]{', '.join(char_data.inventory)}\n"
            
        return payload