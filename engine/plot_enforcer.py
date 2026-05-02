import logging
from pydantic import BaseModel, Field
from clients.robust_caller import RobustCaller

logger = logging.getLogger(__name__)

class EnforcerEvaluation(BaseModel):
    is_approved: bool = Field(..., description="是否完全符合逻辑闭环与战力设定。只要有任何一丝违背，必须设为False")
    violation_report: str = Field(..., description="如果未通过，列出具体的违规点（如：使用了不存在的物品，跨级杀敌等）。通过则留空。")
    correction_guidelines: str = Field(..., description="给作者的强硬修改指令。必须明确指出要删改哪一段落。通过则留空。")

class PlotEnforcer:
    """剧情纪律执行官 (Critic)，负责拦截逻辑毒药"""
    def __init__(self, caller: RobustCaller):
        self.caller = caller

    def evaluate_draft(self, draft_json: str, state_json: str, lore_json: str) -> EnforcerEvaluation:
        logger.info("Enforcer (Critic) 介入：正在对本章草稿进行逻辑拆解审查...")
        
        system_prompt = """
        你是一个极度严苛、不通人情的逻辑审判官（Critic）。
        你的职责是审查小说章节的生成草稿，拦截任何可能导致“战力崩坏”、“物品虚空产生”或“OOC”的毒药数据。
        
        【审查铁律】
        1. 搜身检查：检查补丁中消耗的物品，主角当前身上到底有没有？没有则驳回！
        2. 战力检查：主角的战斗表现是否超越了所在设定的上限？越阶则驳回！
        3. 法则检查：是否触犯了世界观绝对禁忌？触犯则驳回！
        
        你的回答决定了该草稿是落盘还是被打回重写。宁可错杀，不可放过。
        """

        user_prompt = f"""
        【世界观法则】\n{lore_json}
        【主角当前真实状态】\n{state_json}
        
        【待审查草稿 (包含正文与申请的补丁)】\n{draft_json}
        
        请进行严格审查，并输出 JSON 评估结果。
        """

        evaluation = self.caller.ask_for_structured_data(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=EnforcerEvaluation,
            max_repairs=2 # 审查本身逻辑较简单，修复次数可略低
        )
        return evaluation