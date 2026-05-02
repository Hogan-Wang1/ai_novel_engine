import json
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field, ValidationError

# 引入基础组件
from clients.robust_caller import RobustCaller

logger = logging.getLogger("Engine-CoPilot.OutlineArchitect")

class ChapterNode(BaseModel):
    """Pydantic 强校验：大纲节点必须包含的具体元素"""
    chapter_index: int = Field(..., description="本卷中的章节序号，从1开始")
    title: str = Field(..., description="章节标题")
    main_conflict: str = Field(..., description="本章的核心矛盾或目标")
    foreshadowing: str = Field(..., description="本章埋下的伏笔或需要回收的前文线索")
    involved_characters: List[str] = Field(..., description="本章出场的核心角色列表")
    location: str = Field(..., description="本章发生的主要地点")

class VolumeOutline(BaseModel):
    """卷级大纲结构"""
    volume_title: str = Field(..., description="本卷卷名")
    chapters: List[ChapterNode] = Field(..., description="本卷包含的所有章节详细大纲")

class OutlineArchitect:
    def __init__(self, llm_client: RobustCaller, config_data: Dict[str, Any]):
        self.llm = llm_client
        self.config = config_data
        
    def generate_volume_outline(self, volume_number: int) -> List[Dict[str, Any]]:
        """
        卷级大纲生成器：利用黑盒逻辑推演，一次性生成一卷的高致密大纲。
        """
        meta = self.config.get("project_meta", {})
        chapters_per_volume = meta.get("chapters_per_volume", 20)
        
        logger.info(f"🏗️ 正在构筑第 {volume_number} 卷大纲，目标章节数: {chapters_per_volume}章...")
        
        system_prompt = self._build_architect_system_prompt()
        user_prompt = self._build_architect_user_prompt(volume_number, chapters_per_volume, meta)

        # 容错重试机制：大纲是全书基石，允许更多重试次数
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                raw_response = self.llm.call(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7, # 大纲需要一定的创造力和发散性
                    response_format={"type": "json_object"}
                )
                
                # 清洗 Markdown 标记并解析 JSON
                cleaned_json = self._clean_json(raw_response)
                parsed_data = json.loads(cleaned_json)
                
                # 使用 Pydantic 进行严苛的结构验证
                validated_outline = VolumeOutline(**parsed_data)
                
                logger.info(f"✅ 第 {volume_number} 卷大纲生成成功！共 {len(validated_outline.chapters)} 章。")
                
                # 转换为标准字典列表供 Orchestrator 使用
                return [chapter.model_dump() for chapter in validated_outline.chapters]

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"⚠️ 大纲格式解析失败 (Attempt {attempt}/{max_retries}): {str(e)[:200]}")
            except Exception as e:
                logger.error(f"❌ 大纲架构师内部异常 (Attempt {attempt}/{max_retries}): {str(e)}")
        
        logger.critical(f"🛑 第 {volume_number} 卷大纲生成彻底失败，超出最大重试次数。")
        return []

    def _build_architect_system_prompt(self) -> str:
        box = self.config.get("world_bounding_box", {})
        return f"""You are a master-level Narrative Architect. Your task is to design a highly cohesive, logical volume outline for a novel.
You MUST output strictly in JSON format corresponding to the requested structure.

[WORLD BOUNDING BOX]
Tone: {box.get('global_tone')}
Power Ceiling: {box.get('power_ceiling')}
Forbidden Tropes: {', '.join(box.get('forbidden_tropes', []))}

Ensure the pacing follows the 'Save the Cat' beat sheet methodology: setup, rising action, climax, and resolution within this volume."""

    def _build_architect_user_prompt(self, vol_num: int, target_chapters: int, meta: dict) -> str:
        return f"""
Project: {meta.get('title')}
Target Volume: Volume {vol_num}
Total Chapters Required in this Volume: {target_chapters}

Design the outline for Volume {vol_num}. Each chapter must cleanly transition into the next. 
Ensure character motivations are clear and conflict steadily escalates.

Required JSON Structure:
{{
  "volume_title": "<String>",
  "chapters": [
    {{
      "chapter_index": <Int>,
      "title": "<String>",
      "main_conflict": "<String>",
      "foreshadowing": "<String>",
      "involved_characters": ["<Char1>", "<Char2>"],
      "location": "<String>"
    }}
  ]
}}
"""

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()