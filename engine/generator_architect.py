import logging
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from clients.robust_caller import RobustCaller
from memory.state_tracker import GlobalState, CharacterState, Item, Relationship

logger = logging.getLogger(__name__)

# ==========================================
# 创世数据结构 (Genesis Blueprints)
# ==========================================

class PlotMilestone(BaseModel):
    milestone_id: str = Field(..., description="节点ID，格式必须如 ARC1_M1")
    description: str = Field(..., description="必须发生的关键剧情节点，限50字以内")
    is_completed: bool = Field(default=False)

class StoryArc(BaseModel):
    arc_id: str = Field(..., description="卷ID，如 ARC_1")
    arc_name: str = Field(..., description="卷名")
    target_chapter_count: int = Field(..., description="本卷预计跨越的章数，如 30")
    milestones: List[PlotMilestone] = Field(..., description="本卷必须按顺序完成的里程碑清单")

class WorldLore(BaseModel):
    power_levels: List[str] = Field(..., description="境界/战力等级的严格顺序数组，必须从最低到最高排列")
    currency_system: str = Field(..., description="世界货币设定及兑换比例")
    forbidden_rules: List[str] = Field(..., description="防止逻辑崩坏的绝对禁忌（如：跨越两个大境界绝对无法破防、死人绝对不可复活等）")

class ArchitectBlueprint(BaseModel):
    """Architect 最终输出的结构化建筑图纸"""
    lore_bounds: WorldLore
    arcs: List[StoryArc]
    initial_state: GlobalState  # 直接对齐 StateTracker 的状态约束

# ==========================================
# 核心生成器类
# ==========================================

class GeneratorArchitect:
    """
    世界观与大纲架构师：负责将人类的软文本大纲“编译”为硬约束 JSON 图纸。
    仅在项目初始化（冷启动）时被调用一次。
    """
    def __init__(self, robust_caller: RobustCaller):
        self.caller = robust_caller

    def _get_architect_prompt(self) -> str:
        """重火力系统提示词，确立架构师的冰冷逻辑"""
        return """
        你是一个冷酷、严谨、没有感情的顶级小说世界观架构师兼底层逻辑引擎。
        你的唯一任务是将人类提供的模糊小说草案，拆解、编译为一套极其严密的 JSON 约束逻辑。
        
        【最高指令与逻辑锁】
        1. 战力阶梯约束 (power_levels)：必须是一个严格的字符串数组。绝对禁止模糊不清的等级。
        2. 初始面板极简原则 (initial_state)：必须为主角提取一个绝对“干净”的初始面板。只允许拥有大纲开局时明确说明的物品和境界，绝不允许提前把后期的金手指或装备写入初始 inventory。
        3. 物理法则锁 (forbidden_rules)：提取 3-5 条底层法则，这些法则是后续防止 AI 写作“战力膨胀”和“机械降神”的标尺。必须写得极其绝对。
        4. 里程碑驱动 (arcs)：将整个大纲合理切割为若干卷 (StoryArc)。每卷必须设定 3-5 个具体的、可被验证的里程碑 (PlotMilestone)。
        
        你输出的 JSON 决定了整个引擎在接下来 30 万字运行中的生死，绝不可有任何结构偏差。
        """

    def compile_world_blueprint(self, raw_outline: str) -> ArchitectBlueprint:
        """
        执行编译动作
        :param raw_outline: 人类作者提供的原始大纲文本
        :return: 经过严格校验的 ArchitectBlueprint 数据对象
        """
        logger.info("GeneratorArchitect 启动：开始执行创世编译...")
        
        system_prompt = self._get_architect_prompt()
        user_prompt = f"【人类作者原始大纲】\n{raw_outline}\n\n请严格按照要求执行编译，输出 ArchitectBlueprint JSON。"

        try:
            # 依赖防爆网关，强制获取合法结构
            blueprint = self.caller.ask_for_structured_data(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=ArchitectBlueprint,
                max_repairs=3
            )
            logger.info(f"世界观蓝图编译成功！共划定 {len(blueprint.arcs)} 卷，确立了 {len(blueprint.lore_bounds.power_levels)} 个战力阶层。")
            return blueprint
        except Exception as e:
            logger.critical(f"创世编译失败，蓝图解析崩溃: {e}")
            raise