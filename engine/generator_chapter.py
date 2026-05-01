import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError

# 假设这些是你的本地模块
from clients.robust_caller import LLMRouter, RobustCaller
from memory.state_tracker import StateTracker
from memory.recap_manager import RecapManager
from utils.text_cleaner import extract_json_from_text

logger = logging.getLogger("Engine-CoPilot.ChapterGenerator")

class ChapterOutputModel(BaseModel):
    """Pydantic 模型：用于强制校验 LLM 的输出结构，防止格式雪崩"""
    logic_chain: str = Field(..., description="对大纲的解析和接续上一章末尾的逻辑推理")
    character_states_check: str = Field(..., description="检查当前出场角色是否符合人设与战力限制")
    chapter_content: str = Field(..., description="小说的正文内容，必须大于 2000 字")
    end_anchor: str = Field(..., description="本章结尾的悬念或动作，用于下一章的无缝拼接")

class ChapterGenerator:
    def __init__(self, llm_caller: RobustCaller, state_tracker: StateTracker, recap_manager: RecapManager):
        self.llm = llm_caller
        self.state_tracker = state_tracker
        self.recap_manager = recap_manager

    def generate_chapter(self, chapter_index: int, outline_node: Dict[str, Any], prev_tail_text: str) -> Optional[Dict[str, Any]]:
        """
        全自动生成单章内容，包含容错与断点续传思维
        """
        logger.info(f"🚀 正在生成第 {chapter_index} 章: {outline_node.get('title')}")
        
        # 1. 组装极限上下文 (Context Assembly)
        active_characters = self.state_tracker.get_active_characters(outline_node.get("involved_characters", []))
        world_rules = self.state_tracker.get_world_constraints()
        recent_summary = self.recap_manager.get_recent_summary(window_size=3)

        # 2. 构造重火力 Prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            outline_node, prev_tail_text, active_characters, world_rules, recent_summary
        )

        # 3. 带自愈合逻辑的 LLM 调用 (最大重试 3 次)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.debug(f"尝试第 {attempt + 1}/{max_retries} 次请求...")
                raw_response = self.llm.call(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.85, # 保持一定的文学创造性
                    response_format={"type": "json_object"} # 如果 API 支持
                )
                
                # 4. 清洗与解析
                cleaned_json_str = extract_json_from_text(raw_response)
                parsed_data = json.loads(cleaned_json_str)
                
                # 5. Pydantic 强校验 (防漏字段、防数据类型错误)
                validated_data = ChapterOutputModel(**parsed_data)
                
                logger.info(f"✅ 第 {chapter_index} 章生成成功，字数: {len(validated_data.chapter_content)}")
                
                # 更新记忆流
                self.recap_manager.add_chapter_summary(chapter_index, validated_data.chapter_content)
                self.state_tracker.update_entities_from_text(validated_data.chapter_content)
                
                return validated_data.model_dump()

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"⚠️ 解析或校验失败 (Attempt {attempt + 1}): {str(e)}")
                # 在重试前，将错误信息喂回给 LLM 也是一种高级策略 (Reflection)
            except Exception as e:
                logger.error(f"❌ 严重系统错误 (Attempt {attempt + 1}): {str(e)}")
        
        logger.critical(f"🛑 第 {chapter_index} 章生成彻底失败，超出最大重试次数。")
        return None

    def _build_system_prompt(self) -> str:
        # 实际项目中应从 config/prompts_template 加载
        return """You are a master-level novelist and black-box narrative engine. 
Your ONLY goal is to output a perfect JSON object following the exact schema provided.
NEVER output Markdown code blocks, greetings, or explanations outside the JSON.
Adhere strictly to the world's power levels and character logic. Negative Prompt: No sudden personality shifts, no deus ex machina, no breaking the 4th wall."""

    def _build_user_prompt(self, outline, prev_tail, chars, rules, summary) -> str:
        # 具体实现参考下方的 Prompt 模板
        pass