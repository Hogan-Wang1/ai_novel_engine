import logging
from pydantic import BaseModel, Field
from clients.robust_caller import RobustCaller
from memory.state_tracker import StatePatch

logger = logging.getLogger(__name__)

class ChapterDraft(BaseModel):
    """章节草稿，包含正文文本与机器可读的补丁"""
    chapter_title: str = Field(..., description="本章标题")
    content: str = Field(..., description="本章正文内容，需具备纯正文学性，2000-3000字，绝不可带有任何 Markdown 或系统说明。")
    state_patch: StatePatch = Field(..., description="本章导致的剧情与主角状态变动字典")

class GeneratorChapter:
    """负责具体章节生成的 Actor (创作者)"""
    def __init__(self, caller: RobustCaller):
        self.caller = caller

    def _build_system_prompt(self, world_lore_json: str) -> str:
        return f"""
        你是一个顶级的网络小说金牌作者。你的任务是根据提供的上下文，撰写极具沉浸感的章节正文，并输出准确的状态同步补丁。
        
        【世界观铁律（不可违背）】
        {world_lore_json}
        
        【写作准则】
        1. 动作描写必须符合当前境界，严禁跨越战力阶层。
        2. 不要使用“总而言之”、“然而”等AI味浓重的总结词。
        3. 推动剧情向“当前里程碑”发展，不要水字数。
        """

    def generate_draft(self, context_payload: dict, feedback: str = None) -> ChapterDraft:
        """
        生成章节草稿。如果 feedback 不为空，说明这是被 Critic 打回重写的回炉操作。
        """
        logger.info("Generator (Actor) 开始撰写本章草稿...")
        
        system_prompt = self._build_system_prompt(context_payload.get("lore", "{}"))
        
        user_prompt = f"""
        【当前主角面板与近期摘要】
        {context_payload.get("state", "{}")}
        
        【当前卷宗里程碑目标】
        {context_payload.get("current_milestone", "未提供")}
        """
        
        if feedback:
            logger.warning("接收到审判庭退回意见，正在进行修正重写...")
            user_prompt += f"\n\n【审判庭驳回意见（必须立刻修正）】\n{feedback}\n请吸取教训，重新生成完全合规的章节正文与补丁。"

        # 利用阶段二的防爆网关，强制输出包含正文和补丁的完整 JSON
        draft = self.caller.ask_for_structured_data(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ChapterDraft,
            max_repairs=3
        )
        return draft
    
# 在 generator_chapter.py 中
    def generate_draft(self, assembled_prompts: dict, feedback: str = None) -> ChapterDraft:
        system_prompt = assembled_prompts["system"]
        user_prompt = assembled_prompts["user"]
        
        if feedback:
            user_prompt += f"\n\n【审判庭驳回意见（必须立刻修正）】\n{feedback}\n严格遵循此意见重写正文与补丁！"

        return self.caller.ask_for_structured_data(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ChapterDraft,
            max_repairs=3
        )