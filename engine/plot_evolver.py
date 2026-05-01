import json
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("Engine-PlotEvolver")

class PlotNode(BaseModel):
    """单章剧情节点指令"""
    chapter_id: int
    title: str
    conflict_point: str = Field(..., description="本章必须爆发的核心冲突")
    required_stamps: List[str] = Field(..., description="本章必须达成的状态机变更（如：获得道具X）")
    hidden_clues: List[str] = Field(default_factory=list, description="本章需要埋下的伏笔")

class PlotEvolver:
    """大纲裂变器：将粗纲递归拆解为精纲"""
    def __init__(self, llm_client, initial_outline: str):
        self.llm = llm_client
        self.rough_outline = initial_outline
        self.detailed_plan: Dict[int, PlotNode] = {}

    def expand_volume_plan(self, start_chapter: int, end_chapter: int) -> List[PlotNode]:
        """
        调用 LLM 将一段粗略剧情裂变为具体的章节节点。
        """
        logger.info(f"🌀 正在将第 {start_chapter}-{end_chapter} 章的剧情进行递归裂变...")
        
        prompt = f"""
        【原始粗纲】：{self.rough_outline}
        【裂变区间】：第 {start_chapter} 章 至 第 {end_chapter} 章
        
        请将上述区间拆解为具体的单章指令。每章必须包含一个不重复的冲突点，并严格符合状态机逻辑。
        必须输出为 JSON 数组，格式参考：
        [{{ "chapter_id": {start_chapter}, "title": "...", "conflict_point": "...", "required_stamps": ["..."], "hidden_clues": ["..."] }}]
        """
        
        response = self.llm.generate(prompt, response_format={"type": "json_object"})
        nodes_data = json.loads(response).get("chapters", [])
        
        nodes = [PlotNode(**node) for node in nodes_data]
        for node in nodes:
            self.detailed_plan[node.chapter_id] = node
        return nodes

    def get_instruction_for_chapter(self, chapter_id: int) -> PlotNode:
        """获取特定章节的剧情指令"""
        return self.detailed_plan.get(chapter_id)