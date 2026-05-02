import os
import json
import logging
import time
from typing import Dict, Any, List

# 导入核心组件 (假设均已实现)
from engine.context_assembler import ContextAssembler
from engine.generator_chapter import ChapterGenerator
from engine.plot_evolver import PlotEnforcer # 此处对应之前定义的裁决者
from memory.state_tracker import StateTracker
from memory.recap_manager import RecapManager

logger = logging.getLogger("Engine-CoPilot.Orchestrator")

class NovelOrchestrator:
    def __init__(
        self, 
        config_path: str,
        assembler: ContextAssembler,
        generator: ChapterGenerator,
        enforcer: PlotEnforcer,
        state_tracker: StateTracker,
        recap_manager: RecapManager,
        output_dir: str = "./output/workspaces"
    ):
        self.assembler = assembler
        self.generator = generator
        self.enforcer = enforcer
        self.state_tracker = state_tracker
        self.recap_manager = recap_manager
        
        # 基础配置
        self.config = self.assembler.config
        self.max_retries = self.config.get("engine_parameters", {}).get("max_retries_per_chapter", 3)
        self.output_dir = output_dir
        self.checkpoint_file = os.path.join(self.output_dir, "checkpoint.json")
        
        os.makedirs(self.output_dir, exist_ok=True)

    def _load_checkpoint(self) -> int:
        """读取断点，返回下一个需要生成的章节索引"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    last_chapter = data.get("last_successful_chapter", 0)
                    logger.info(f"💾 发现断点记录，将从第 {last_chapter + 1} 章恢复生成。")
                    return last_chapter + 1
            except Exception as e:
                logger.warning(f"⚠️ 断点文件损坏，将从头开始: {str(e)}")
        return 1

    def _save_checkpoint(self, chapter_index: int):
        """持久化当前进度"""
        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump({"last_successful_chapter": chapter_index, "timestamp": time.time()}, f)

    def run_pipeline(self, full_outline: List[Dict[str, Any]]):
        """
        主引擎心跳：启动无人值守的流水线
        """
        start_chapter = self._load_checkpoint()
        total_chapters = len(full_outline)

        logger.info(f"🚀 [主引擎点火] 目标进度: {start_chapter}/{total_chapters}")

        for current_idx in range(start_chapter, total_chapters + 1):
            outline_node = full_outline[current_idx - 1] # 索引对齐
            
            # 获取物理锚点（上一章结尾）
            prev_tail = self.recap_manager.get_previous_tail(current_idx)
            
            # 组装本章上下文
            context = self.assembler.build_generation_context(current_idx, outline_node, prev_tail)
            
            success = False
            critic_feedback = None # 用于承载打回重写的指令

            # --- 对抗式生成循环 (Adversarial Loop) ---
            for attempt in range(1, self.max_retries + 1):
                logger.info(f"🔄 正在生成第 {current_idx} 章 (尝试 {attempt}/{self.max_retries})...")
                
                # 如果有之前打回的意见，强行注入到 context 的 user_prompt 顶部
                current_context = context.copy()
                if critic_feedback:
                    warning_prefix = f"【CRITICAL REWRITE INSTRUCTION】上一版被裁决者驳回，你必须遵循以下修改指令：\n{critic_feedback}\n\n"
                    current_context["user_prompt"] = warning_prefix + current_context["user_prompt"]

                # 1. 生成正文
                generated_data = self.generator.generate_chapter(
                    system_prompt=current_context["system_prompt"],
                    user_prompt=current_context["user_prompt"]
                )
                
                if not generated_data:
                    logger.error("❌ 生成器返回空数据，触发重试。")
                    continue

                chapter_text = generated_data.get("chapter_content", "")
                
                # 2. 四维矩阵裁决
                eval_result = self.enforcer.evaluate_chapter(
                    outline=json.dumps(outline_node, ensure_ascii=False),
                    state_snapshot=self.state_tracker.get_current_snapshot_str(),
                    world_box=json.dumps(self.config.get("world_bounding_box"), ensure_ascii=False),
                    generated_text=chapter_text
                )

                if eval_result.final_decision == "PASS":
                    logger.info(f"✅ 第 {current_idx} 章裁决通过！准备落盘。")
                    
                    # 3. 内存与状态流转 (State Update)
                    self._commit_chapter(current_idx, generated_data)
                    success = True
                    break # 跳出重试循环，进入下一章
                else:
                    critic_feedback = eval_result.rewrite_instructions
                    logger.warning(f"⚠️ 第 {current_idx} 章被打回！正在将修改指令反馈给生成器...")
                    time.sleep(2) # API 避退

            # --- 熔断保护 ---
            if not success:
                logger.critical(f"🛑 致命错误：第 {current_idx} 章在 {self.max_retries} 次重试后彻底失败。流水线熔断。")
                logger.critical("请人工介入检查大纲是否过于矛盾，或调低 Critic 的严苛度。")
                break # 彻底终止流水线

        if start_chapter > total_chapters:
            logger.info("🎉 全书生成完毕！引擎平稳停机。")

    def _commit_chapter(self, chapter_index: int, generated_data: Dict[str, Any]):
        """执行落盘与记忆更新操作"""
        # 1. 写入本地 TXT 文件供用户阅读
        chapter_title = f"第 {chapter_index} 章" # 简化处理，实际应从大纲取
        file_path = os.path.join(self.output_dir, f"Chapter_{chapter_index:03d}.txt")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"## {chapter_title}\n\n")
            f.write(generated_data.get("chapter_content", ""))
        
        # 2. 更新双轨记忆系统 (由各个 Manager 内部处理 LLM 调用)
        # 提取上一章末尾 500 字存入 Recap
        self.recap_manager.update_tail(chapter_index, generated_data.get("end_anchor", ""))
        # 提取事件摘要存入 VectorDB
        self.recap_manager.extract_and_store_summary(chapter_index, generated_data.get("chapter_content", ""))
        # 更新角色状态卡
        self.state_tracker.update_entities_from_text(generated_data.get("chapter_content", ""))

        # 3. 记录断点
        self._save_checkpoint(chapter_index)