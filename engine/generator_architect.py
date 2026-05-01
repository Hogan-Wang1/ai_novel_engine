from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional
from loguru import logger

# ==========================================
# 逻辑锁基类：世界观与战力天花板强制校验
# ==========================================
class PowerSystemRule(BaseModel):
    tier_name: str = Field(..., description="境界/战力等级名称，例如：结丹期 / 赛博精神病一阶")
    power_limit: str = Field(..., description="该境界的破坏力上限描述，严禁越级。例如：最大摧毁一栋房屋")
    taboo: str = Field(..., description="该境界的绝对禁忌或代价，例如：使用过度会导致记忆丧失")

class WorldConstraints(BaseModel):
    """
    黑盒生成的世界观底层逻辑锁，整个百万字生成周期内绝对不可篡改。
    """
    world_name: str = Field(..., description="世界名称")
    core_conflict: str = Field(..., description="贯穿百万字的核心矛盾")
    power_levels: List[PowerSystemRule] = Field(..., min_length=3, description="战力体系设定，必须严格按递进排序")
    banned_tropes: List[str] = Field(
        default=["战力崩坏", "机械降神", "主角突然降智", "无代价复活"],
        description="黑名单：绝对不允许在小说中出现的烂俗桥段"
    )

# ==========================================
# 章节级逻辑锁：防止剧情水化与 OOC
# ==========================================
class ChapterOutlineLock(BaseModel):
    """
    每一章生成正文前，必须先由推理模型(R1)产出并校验此结构。
    """
    chapter_number: int
    chapter_title: str
    pov_character: str = Field(..., description="本章主要视角人物")
    plot_advancement: str = Field(..., description="本章对主线剧情的实质性推进（不能少于50字）")
    character_arc_shift: Optional[str] = Field(None, description="人物心理/性格的微小转变")
    
    # 状态机硬校验字段
    violates_world_rules: bool = Field(..., description="AI自我反思：本章大纲是否违反了 WorldConstraints 中的战力或禁忌？")
    ooc_risk_assessment: float = Field(..., ge=0.0, le=1.0, description="OOC风险评估(0-1)。大于0.3将触发重新生成")

    @field_validator("violates_world_rules")
    def strict_rule_check(cls, v):
        if v is True:
            logger.error("逻辑锁触发：模型自我检测到违背世界观设定，强制抛出异常以触发 Tenacity 重试！")
            raise ValueError("Draft violates core world rules. Must regenerate.")
        return v

    @field_validator("ooc_risk_assessment")
    def ooc_threshold_check(cls, v):
        if v > 0.3:
            logger.error(f"逻辑锁触发：OOC风险过高 ({v})，强制抛出异常以触发 Tenacity 重试！")
            raise ValueError(f"OOC risk ({v}) exceeds threshold of 0.3. Regenerate outline.")
        return v

# ==========================================
# 架构师类：对外暴露的调用入口
# ==========================================
class GeneratorArchitect:
    def __init__(self, router_client):
        """
        :param router_client: 上一步编写的 DeepSeekRouter 实例
        """
        self.client = router_client

    async def build_world_base(self, super_prompt: str) -> WorldConstraints:
        """
        根据超级提示词，生成并锁死世界观 JSON。
        底层调用了 robust_caller 中的 generate_structured_data，若返回不符合 WorldConstraints，将自动重试。
        """
        system_prompt = "你是一个严谨的世界观架构师。你的任务是根据用户的灵感，构建一个逻辑严密的设定。你必须严格思考战力平衡与规则代价。"
        
        # 将 Pydantic 模型作为目标强校验格式传入
        world_data = await self.client.generate_structured_data(
            system_prompt=system_prompt,
            user_prompt=super_prompt,
            response_model=WorldConstraints,
            temperature=0.3 # 极低温度，保证逻辑锁不变形
        )
        return world_data