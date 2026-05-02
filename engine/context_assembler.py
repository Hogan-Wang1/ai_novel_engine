import logging
from typing import Dict, Any, List
import yaml

# 引入之前的抽象模块
from memory.state_tracker import StateTracker
from memory.recap_manager import RecapManager
from memory.vector_db_client import VectorDBClient

logger = logging.getLogger("Engine-CoPilot.ContextAssembler")

class ContextAssembler:
    def __init__(
        self, 
        config_path: str,
        state_tracker: StateTracker,
        recap_manager: RecapManager,
        vector_db: VectorDBClient
    ):
        self.config = self._load_run_config(config_path)
        self.state_tracker = state_tracker
        self.recap_manager = recap_manager
        self.vector_db = vector_db

    def _load_run_config(self, path: str) -> Dict[str, Any]:
        """加载创世神全局配置"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.critical(f"🛑 创世配置文件加载失败: {str(e)}")
            raise

    def build_generation_context(self, chapter_index: int, current_outline: Dict[str, Any], prev_tail_text: str) -> Dict[str, str]:
        """
        核心方法：拼装高信噪比的 '三明治' Context。
        返回 system_prompt 和 user_prompt。
        """
        logger.info(f"🧩 正在组装第 {chapter_index} 章的上下文...")

        # ================= 1. 提取动态记忆 (Dynamic Memory) =================
        involved_chars = current_outline.get("involved_characters", [])
        location = current_outline.get("location", "未知")
        
        # 1.1 热记忆：当前角色的绝对状态（血量、装备、好感度）
        active_states = self.state_tracker.get_entities_snapshot(involved_chars)
        
        # 1.2 冷记忆：滑动窗口摘要 (最近 3 章) + 向量检索伏笔
        recent_summaries = self.recap_manager.get_recent_summary(window_size=3)
        lore_context = self.vector_db.search_relevant_lore(query=f"{' '.join(involved_chars)} {location}", top_k=2)

        # ================= 2. 构建顶层系统指令 (System Prompt) =================
        system_prompt = self._build_system_prompt()

        # ================= 3. 构建底层执行指令 (User Prompt) =================
        user_prompt = self._build_user_prompt(
            active_states=active_states,
            recent_summaries=recent_summaries,
            lore_context=lore_context,
            current_outline=current_outline,
            prev_tail_text=prev_tail_text
        )

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }

    def _build_system_prompt(self) -> str:
        """组装绝对不可违背的世界法则"""
        lang_map = self.config.get("linguistic_mapping", {})
        world_box = self.config.get("world_bounding_box", {})
        
        return f"""You are the core generator of an automated narrative engine. 
Your output MUST strictly follow the JSON schema provided.

[ABSOLUTE LINGUISTIC RULES]
- Dialogue Language: {lang_map.get('dialogue_language')}
- Narration Language: {lang_map.get('narration_language')}
- Lore Terms: {lang_map.get('lore_terms_language')}

[WORLD BOUNDARIES]
- Global Tone: {world_box.get('global_tone')}
- Power Ceiling: {world_box.get('power_ceiling')}
- Banned Words: {', '.join(world_box.get('banned_words', []))}

You must NOT break character states. You must NOT introduce Deus ex machina."""

    def _build_user_prompt(self, active_states, recent_summaries, lore_context, current_outline, prev_tail_text) -> str:
        """组装带有物理锚点的任务执行指令"""
        return f"""
### [COLD MEMORY] RECENT EVENTS & LORE
{recent_summaries}
Relevant Lore: {lore_context}

### [HOT MEMORY] CURRENT ENTITY STATES
{active_states}
(Warning: Ensure character actions in this chapter strictly align with these physical/mental states.)

### [PHYSICAL ANCHOR] PREVIOUS CHAPTER TAIL
{prev_tail_text}
(Instruction: Your generation MUST seamlessly continue exactly from the end of this text.)

### [CURRENT TARGET] CHAPTER OUTLINE
Title: {current_outline.get('title')}
Main Conflicts: {current_outline.get('main_conflict')}
Foreshadowing to plant: {current_outline.get('foreshadowing')}

Proceed to generate the chapter JSON (logic_chain, character_states_check, chapter_content, end_anchor).
"""