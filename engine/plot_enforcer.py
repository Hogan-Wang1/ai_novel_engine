import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

# 假设这些是你的本地模块
from clients.robust_caller import RobustCaller

logger = logging.getLogger("Engine-CoPilot.PlotEnforcer")

class DimensionEval(BaseModel):
    passed: bool = Field(..., description="该维度是否及格")
    reason: str = Field(..., description="一句话解释为何及格或不及格")

class EnforcerResult(BaseModel):
    """大纲裁决者的强类型输出模型"""
    eval_plot: DimensionEval = Field(..., description="剧情执行力评估")
    eval_lore: DimensionEval = Field(..., description="战力与世界观评估")
    eval_state: DimensionEval = Field(..., description="状态继承评估")
    eval_linguistic: DimensionEval = Field(..., description="双语结构纪律评估")
    
    final_decision: str = Field(..., description="必须是 'PASS' 或 'REJECT'")
    rewrite_instructions: Optional[str] = Field(None, description="如果 REJECT，提供给 Generator 的一击必杀修改指令；如果 PASS，填 null")

class PlotEnforcer:
    def __init__(self, llm_caller: RobustCaller):
        self.llm = llm_caller

    def evaluate_chapter(
        self, 
        outline: str, 
        state_snapshot: str, 
        world_box: str, 
        generated_text: str
    ) -> EnforcerResult:
        """
        核心评估方法：将生成的文本放入四维矩阵中进行生死裁决。
        """
        logger.info("⚖️ 正在启动四维矩阵裁决 (Plot Enforcer)...")

        # 此处应从 YAML 读取 system_msg 和 user_msg，此处为简化示意
        system_msg = "..." # (加载上面 YAML 中的 system 部分)
        user_msg = "..."   # (加载 user_template 并用参数 format)

        try:
            raw_response = self.llm.call(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.1,  # 裁决者不需要创造力，需要绝对的冰冷与理智
                response_format={"type": "json_object"}
            )
            
            # 清洗并解析 JSON
            parsed_data = json.loads(self._clean_json(raw_response))
            result = EnforcerResult(**parsed_data)
            
            # 日志输出裁决结果
            if result.final_decision == "PASS":
                logger.info("✅ 裁决通过：章节符合全局纪律。")
            else:
                logger.warning(f"❌ 裁决驳回！原因集:")
                if not result.eval_plot.passed: logger.warning(f"  - 剧情违规: {result.eval_plot.reason}")
                if not result.eval_lore.passed: logger.warning(f"  - 战力违规: {result.eval_lore.reason}")
                if not result.eval_state.passed: logger.warning(f"  - 状态违规: {result.eval_state.reason}")
                if not result.eval_linguistic.passed: logger.warning(f"  - 格式违规: {result.eval_linguistic.reason}")
                logger.warning(f"🔄 注入重写指令: {result.rewrite_instructions}")
                
            return result

        except Exception as e:
            logger.error(f"🛑 裁决器内部系统崩溃: {str(e)}")
            # 容错降级策略：如果裁决器自身宕机，为了防止流水线断裂，可以选择默认放行（视严格程度而定）
            raise e

    def _clean_json(self, text: str) -> str:
        """移除可能存在的 Markdown JSON 标记"""
        return text.replace("```json", "").replace("```", "").strip()