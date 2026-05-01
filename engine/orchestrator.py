import os
import asyncio
from loguru import logger
from typing import Optional

# 导入我们前期构建的基础设施
from clients.robust_caller import DeepSeekRouter
from engine.generator_architect import GeneratorArchitect, ChapterOutlineLock
from memory.state_tracker import MemoryManager

# 用于状态抽取的 Pydantic 模型 (确保模型返回结构化的更新指令)
from pydantic import BaseModel, Field

class StateExtractionResult(BaseModel):
    rolling_summary_update: str = Field(..., description="结合本章内容，更新后的最近5万字剧情摘要(限800字以内)")
    key_events_for_rag: list[str] = Field(..., description="本章发生的3-5个核心原子事件，用于存入向量数据库")

class NarrativeOrchestrator:
    """
    黑盒流水线总调度中枢：无情地驱动剧情向前滚动
    """
    def __init__(self):
        logger.info("初始化 NarrativeOrchestrator 中枢...")
        # 1. 挂载深渊路由 (网络与模型调度层)
        self.router = DeepSeekRouter()
        # 2. 挂载架构师 (逻辑锁校验层)
        self.architect = GeneratorArchitect(self.router)
        # 3. 挂载记忆体 (状态机与 RAG 检索层)
        self.memory = MemoryManager()

    async def _generate_chapter_outline(self, chapter_index: int, context_payload: str) -> ChapterOutlineLock:
        """步骤一：结合当前绝对真理，生成被逻辑锁焊死的章节大纲"""
        logger.info(f"开始构思第 {chapter_index} 章大纲...")
        
        system_prompt = (
            "你是一个极其严谨的剧情推演大师。你必须根据当前的【绝对真理上下文】，"
            "推演出逻辑严密、严禁越级、符合人物心理的下一章大纲。"
        )
        user_prompt = f"{context_payload}\n\n请推演第 {chapter_index} 章的具体剧情大纲。"
        
        # 强制走 Reasoning 模型 (R1) 和 Pydantic 强校验
        outline = await self.router.generate_structured_data(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ChapterOutlineLock,
            temperature=0.4
        )
        logger.success(f"第 {chapter_index} 章大纲逻辑锁校验通过：{outline.chapter_title}")
        return outline

    async def _generate_chapter_text(self, outline: ChapterOutlineLock, context_payload: str) -> str:
        """步骤二：基于大纲和上下文，释放生成模型的文学创造力"""
        logger.info(f"开始生成第 {outline.chapter_number} 章正文...")
        
        system_prompt = (
            "你是一位顶级的网文白金大神，文笔极具画面感，对话符合人物性格，战斗描写张力十足。"
            "你必须严格遵循输入的大纲进行扩写，绝对不允许修改大纲既定的剧情走向和结局。"
        )
        user_prompt = (
            f"{context_payload}\n\n"
            f"【本章严格大纲指令】\n"
            f"标题：{outline.chapter_title}\n"
            f"视角人物：{outline.pov_character}\n"
            f"核心推进：{outline.plot_advancement}\n"
            f"人物心理转变：{outline.character_arc_shift or '无特殊转变'}\n\n"
            f"请直接输出正文内容（不少于3000字），不要包含任何废话或解释。"
        )
        
        # 走 Generation 模型 (V3)，提高温度增加修辞丰富度
        text = await self.router.generate_chapter_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.85
        )
        return text

    async def _update_global_memory(self, chapter_index: int, outline: ChapterOutlineLock, chapter_text: str):
        """步骤三：使用推理模型抽取本章核心信息，更新状态机和向量库"""
        logger.info("提取记忆锚点，更新全局状态机...")
        
        system_prompt = "你是冷酷的记忆提取机器。阅读最新章节，更新滚动摘要，并提取原子事件。"
        user_prompt = (
            f"旧版摘要：{self.memory.world_state.rolling_summary}\n\n"
            f"最新章节内容：\n{chapter_text[:2000]}... (截断以节省token)\n\n"
            f"请根据以上内容，执行状态更新抽取。"
        )
        
        extraction = await self.router.generate_structured_data(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=StateExtractionResult,
            temperature=0.2
        )
        
        # 1. 更新 WorldState
        self.memory.world_state.current_chapter_index = chapter_index
        self.memory.world_state.rolling_summary = extraction.rolling_summary_update
        self.memory.save_state()
        
        # 2. 归档到 ChromaDB 向量库
        self.memory.archive_chapter_to_lore(
            chapter_index=chapter_index,
            chapter_summary=outline.plot_advancement,
            key_events=extraction.key_events_for_rag
        )
        logger.success("记忆库与状态机更新完毕。")

    async def run_pipeline(self, super_prompt: str, target_chapters: int = 1000):
        """
        引擎主循环点火入口：无情运转，直到达成目标。
        """
        logger.info("🚀 黑盒叙事引擎开始点火...")
        
        # 1. 检查是否需要生成初始世界观
        if self.memory.world_state.current_chapter_index == 0:
            logger.info("检测到新世界线，开始基建世界观约束...")
            world_constraints = await self.architect.build_world_base(super_prompt)
            # 将世界观基础设定直接打入 RAG 的最深处
            self.memory.archive_chapter_to_lore(0, "世界观底层设定", world_constraints.banned_tropes)
            logger.success(f"世界线 [{world_constraints.world_name}] 确立。")
        else:
            logger.info(f"从第 {self.memory.world_state.current_chapter_index} 章断点续传。")

        # 2. 死亡循环：百万字流水线
        start_index = self.memory.world_state.current_chapter_index + 1
        
        for chapter_idx in range(start_index, target_chapters + 1):
            logger.info(f"========== 纪元轮转：正在处理第 {chapter_idx} 章 ==========")
            
            try:
                # [Phase A] 组装弹药：获取全局真理上下文
                context_payload = self.memory.get_context_payload_for_next_chapter()
                
                # 可选：如果大纲里有暗示，可以在这里调用 self.memory.recall_lore() 注入历史伏笔
                
                # [Phase B] 架构设计：生成被逻辑锁死的大纲
                outline = await self.generate_chapter_outline(chapter_idx, context_payload)
                
                # [Phase C] 铺陈生成：由大纲释放正文
                chapter_text = await self.generate_chapter_text(outline, context_payload)
                
                # [Phase D] 物理落盘：保存正文到本地文件
                output_dir = "./output/chapters"
                os.makedirs(output_dir, exist_ok=True)
                with open(f"{output_dir}/chapter_{chapter_idx:04d}.txt", "w", encoding="utf-8") as f:
                    f.write(f"第{chapter_idx}章 {outline.chapter_title}\n\n")
                    f.write(chapter_text)
                
                # [Phase E] 记忆收束：更新状态机与向量防遗忘层
                await self._update_global_memory(chapter_idx, outline, chapter_text)
                
                logger.success(f"========== 第 {chapter_idx} 章 封卷落盘 ==========\n")
                
            except Exception as e:
                # 最后的终极兜底：如果重试机制都被击穿，记录快照，安全挂起
                logger.error(f"严重系统异常，在第 {chapter_idx} 章坠毁: {e}")
                logger.error("流水线已安全挂起，等待人工核查日志。")
                break

# ==========================================
# 引擎启动器入口
# ==========================================
if __name__ == "__main__":
    import pathlib
    
    # 从外部文件安全读取作者设定的超级提示词
    prompt_path = pathlib.Path("./prompts/super_prompt.md")
    if not prompt_path.exists():
        logger.error(f"点火失败：未找到世界观设定文件 {prompt_path}")
        exit(1)
        
    with open(prompt_path, "r", encoding="utf-8") as f:
        SUPER_PROMPT = f.read()
    
    orchestrator = NarrativeOrchestrator()
    # 异步启动死循环，目标 100 章
    asyncio.run(orchestrator.run_pipeline(super_prompt=SUPER_PROMPT, target_chapters=100))