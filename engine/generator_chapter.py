import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError

# 【依赖收束】只允许导入最高层级的 API 装甲
from clients.robust_caller import RobustCaller

logger = logging.getLogger("Engine-CoPilot.ChapterGenerator")

class ChapterOutputModel(BaseModel):
    """
    Pydantic 模型：强制校验 LLM 输出的 JSON 结构，这是防格式雪崩的最后一道防线。
    """
    logic_chain: str = Field(..., description="对当前大纲的解析和接续上一章末尾的黑盒逻辑推理")
    character_states_check: str = Field(..., description="校验主角状态（如重伤/持有特定道具）将如何影响本章")
    chapter_content: str = Field(..., description="小说正文内容，纯文本结构")
    end_anchor: str = Field(..., description="本章结束时的状态快照（人物位置、心理、面临的直接局势）")

class ChapterGenerator:
    """
    正文生成核心引擎。
    负责将高信噪比的上下文转换为符合法典纪律的小说正文，自带 JSON 自愈合解析。
    """
    def __init__(self, llm_caller: RobustCaller):
        self.llm = llm_caller

    def generate_chapter(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        """
        调用 API 并强制解析为安全的 ChapterOutputModel 结构
        """
        # 在生成正文时，虽然 API 层有重试，但解析 JSON 也需要重试容错
        max_parse_retries = 3 
        
        for attempt in range(1, max_parse_retries + 1):
            try:
                # 触发底层 RobustCaller (自带 429 和网络断连保护)
                raw_response = self.llm.call(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.85, # 保持一定的文学创造性
                    response_format={"type": "json_object"} 
                )
                
                if not raw_response:
                    raise ValueError("API 返回了空响应")

                # 1. 粗洗去噪：剥离可能存在的 Markdown 标记
                cleaned_json_str = self._clean_json(raw_response)
                
                # 2. 强校验：反序列化并进行 Pydantic 字段级验证
                parsed_data = json.loads(cleaned_json_str)
                validated_data = ChapterOutputModel(**parsed_data)
                
                content_length = len(validated_data.chapter_content)
                logger.debug(f"✅ 正文生成与结构校验成功 (字数: {content_length})")
                
                return validated_data.model_dump()

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"⚠️ LLM 输出格式越界 (Attempt {attempt}/{max_parse_retries}) | 解析异常: {str(e)[:150]}")
            except Exception as e:
                logger.error(f"❌ 正文生成器内部发生不可预期的崩溃 (Attempt {attempt}/{max_parse_retries}): {str(e)}")
        
        logger.error("🛑 正文生成器因连续格式错误已熔断，向上层抛出 None 以触发系统级重写。")
        return None

    def _clean_json(self, text: str) -> str:
        """剥离 LLM 喜欢自作主张加上的 ```json 和 ``` 标记"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()