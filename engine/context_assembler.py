import logging
from typing import Dict, List, Any
import json
from memory.state_tracker import GlobalState

logger = logging.getLogger(__name__)

class ContextAssembler:
    """
    动态提示词组装线：负责将静态世界观、动态状态机和里程碑目标，
    无缝熔铸成极具约束力的 LLM Prompt。
    """
    
    def __init__(self):
        # 核心防爆锁：负面词库与 AI 味屏蔽名单
        self.negative_lexicon = [
            "总而言之", "毫无疑问", "不难发现", "宛如", "深邃", "嘴角勾起一抹弧度",
            "倒吸一口凉气", "恐怖如斯", "然而", "可以说", "综上所述"
        ]

    def build_system_prompt(self, lore_json: str) -> str:
        """
        构建系统级 Prompt：确立底层逻辑与负面约束（指令墙）
        """
        negative_words_str = "、".join(self.negative_lexicon)
        
        return f"""
        你是一个冷酷、精准、没有感情的顶级网络小说生成机器（代号 Actor）。
        你没有自我意识，绝不能在正文中与读者对话，绝不能使用系统提示语。

        【世界观底层铁律（不可违背）】
        {lore_json}

        【最高级写作戒律（指令墙）】
        1. 视点约束：严格保持第三人称有限视角，跟随主角推进。
        2. 动作匹配：主角的战力表现必须严格受限于其当前的【等级】和【物品】，绝不允许机械降神或跨阶秒杀。
        3. 文本洁癖（极其重要）：绝不允许在正文中使用以下 AI 味泛滥的词汇或类似表达：[{negative_words_str}]。
        4. 结构要求：正文必须是纯粹的小说文本，禁止输出任何 Markdown 格式（如加粗、标题级别），禁止输出代码块。
        """

    def build_user_prompt(self, state_dict: dict, recent_summaries: List[str], current_milestone: str) -> str:
        """
        构建用户级 Prompt：注入当前面板、记忆窗口与战术目标
        """
        # 1. 解析状态机面板
        chapter_num = state_dict.get("current_chapter", 0) + 1
        protagonist = state_dict.get("protagonist_status", {})
        
        # 2. 组装滑动窗口记忆 (只取最近 3 章，防止远古记忆污染)
        memory_str = "\n".join([f"- {summary}" for summary in recent_summaries[-3:]])
        if not memory_str:
            memory_str = "故事刚刚开局，暂无近期记忆。"

        # 3. 构建高浓度战术指令
        return f"""
        【当前进度】: 第 {chapter_num} 章

        【主角当前实时硬面板 (State Snapshot)】
        - 坐标位置：{protagonist.get('location', '未知')}
        - 战力境界：{protagonist.get('power_level', '未知')}
        - 健康状态：{protagonist.get('health', '未知')}
        - 核心持有物：{', '.join(protagonist.get('inventory', [])) if protagonist.get('inventory') else '空无一物'}

        【前情提要 (最近三章滑动记忆)】
        {memory_str}

        【本章战术目标 (Milestone Engine)】
        当前卷轴最高指令：{current_milestone}
        
        【生成要求】
        请基于以上硬面板和目标，推进剧情，生成本章正文（2000-3000字）。
        注意：你不仅仅是在写文本，你是在推演一个状态机。你的正文必须为接下来你要输出的 `StatePatch` JSON 补丁提供合理的逻辑支撑！
        """

    def assemble_payload(self, lore_json: str, state_json: str, current_milestone: str) -> Dict[str, str]:
        """
        向 Orchestrator 提供最终的组装件
        """
        try:
            state_dict = json.loads(state_json)
            recent_summaries = state_dict.get("recent_events", [])
        except json.JSONDecodeError:
            logger.error("状态机 JSON 解析失败，组装器回退至安全模式。")
            state_dict = {}
            recent_summaries = []

        system_prompt = self.build_system_prompt(lore_json)
        user_prompt = self.build_user_prompt(state_dict, recent_summaries, current_milestone)

        return {
            "system": system_prompt,
            "user": user_prompt
        }