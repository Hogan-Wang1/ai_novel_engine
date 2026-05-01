import json
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# 假设复用您现有项目库中的工具包
# from clients.robust_caller import LLMClient
# from memory.state_tracker import StateTracker
# from memory.vector_db_client import VectorDB

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Engine-Orchestrator")

# 1. 严格定义输出数据结构 (JSON Schema 锁)
class ChapterOutput(BaseModel):
    thought_process: str = Field(..., description="引擎内部思考：剧情连贯性检查、角色动机推演、战力平衡验证")
    state_updates: Dict[str, str] = Field(..., description="对当前世界观、人物状态、持有物品的更新指令")
    summary: str = Field(..., description="本章的精准摘要（用于下一章的上下文拼接）")
    end_hook: str = Field(..., description="本章结尾的平滑过渡锚点（如角色动作、未完对话、场景转移）")
    content: str = Field(..., description="小说的正文内容，至少3000字，不包含任何元信息")

class HallucinationError(Exception):
    """自定义幻觉检测异常"""
    pass

class ChapterGenerator:
    def __init__(self, llm_client, state_tracker, vector_db):
        self.llm = llm_client
        self.state = state_tracker      # 维护角色卡、时间线、战力体系
        self.db = vector_db             # 维护历史章节向量
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        # 加载强约束的系统提示词，详见第二部分
        with open("config/prompts_template/system_prompts.yaml.example", "r", encoding="utf-8") as f: #
            return f.read()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((ValidationError, HallucinationError, json.JSONDecodeError)),
        reraise=True
    )
    def generate_chapter(self, chapter_index: int, previous_summary: str, previous_hook: str) -> ChapterOutput:
        logger.info(f"🚀 开始生成第 {chapter_index} 章...")
        
        # 1. 组装动态上下文 (Algorithm Context Stitching)
        current_world_state = self.state.get_current_snapshot()
        retrieved_lore = self.db.query(previous_summary, top_k=3) 
        
        prompt = self._build_generation_prompt(
            chapter_index, previous_summary, previous_hook, current_world_state, retrieved_lore
        )

        # 2. 调用 LLM 并要求强制输出 JSON
        raw_response = self.llm.generate(
            system_prompt=self.system_prompt,
            user_prompt=prompt,
            response_format={"type": "json_object"} # 强制 JSON 模式
        )

        try:
            # 3. 校验并反序列化输出
            output_data = json.loads(raw_response)
            chapter_data = ChapterOutput(**output_data)
            
            # 4. 前置黑盒逻辑校验 (战力膨胀拦截等)
            self._validate_logic_locks(chapter_data.state_updates, current_world_state)
            
            return chapter_data
            
        except ValidationError as e:
            logger.error(f"❌ JSON结构校验失败，触发重试: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 生成解析异常: {e}")
            raise

    def _build_generation_prompt(self, index: int, summary: str, hook: str, state: dict, lore: list) -> str:
        return f"""
        【当前任务】生成第 {index} 章
        【上一章梗概】{summary}
        【上一章结尾锚点】(必须无缝衔接此动作或场景)：{hook}
        【全局状态机参数】{json.dumps(state, ensure_ascii=False)}
        【相关历史记忆】{lore}
        
        请严格遵循 System Prompt 的约束，输出指定的 JSON 格式。
        """

    def _validate_logic_locks(self, updates: Dict, current_state: Dict):
        # 实现自定义的战力检测、生死状态检测逻辑
        # 如果检测到死亡角色复活或越级秒杀，抛出 HallucinationError 强制重试
        pass

    def run_pipeline(self, target_chapters: int):
        prev_summary = "故事的起点..."
        prev_hook = "主角推开了那扇沉重的大门。"
        
        for i in range(1, target_chapters + 1):
            try:
                chapter = self.generate_chapter(i, prev_summary, prev_hook)
                
                # 持久化存储
                self._save_to_disk(i, chapter.content)
                self.db.insert(chapter.content, metadata={"chapter": i})
                self.state.apply_updates(chapter.state_updates)
                
                # 状态轮转，为下一章做准备 (Zero-intervention smoothing)
                prev_summary = chapter.summary
                prev_hook = chapter.end_hook
                logger.info(f"✅ 第 {i} 章生成并保存成功。")
                
            except Exception as e:
                logger.critical(f"🛑 流水线致命崩溃于第 {i} 章: {e}")
                break