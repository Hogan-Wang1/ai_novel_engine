import os
import json
import logging
import time
from pathlib import Path
from typing import Optional

from clients.robust_caller import RobustCaller
from memory.state_tracker import StateTracker
from engine.context_assembler import ContextAssembler
from engine.generator_architect import GeneratorArchitect
from engine.generator_chapter import GeneratorChapter
from engine.plot_enforcer import PlotEnforcer

logger = logging.getLogger(__name__)

class Orchestrator:
    """
    黑盒叙事引擎总线调度器 (The Black-Box Orchestrator)
    整合所有流水线组件，执行全自动创世与 Actor-Critic 自纠偏推演循环。
    """
    
    def __init__(self, workspace_dir: str, caller: RobustCaller):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 注入核心防爆调用网关
        self.caller = caller
        
        # 2. 实例化记忆中枢与动态组装线
        self.state_tracker = StateTracker(str(self.workspace_dir))
        self.assembler = ContextAssembler()
        
        # 3. 实例化大模型工坊组件
        self.architect = GeneratorArchitect(caller)  # 创世编译器
        self.actor = GeneratorChapter(caller)        # 章节创作者
        self.critic = PlotEnforcer(caller)           # 逻辑审判官
        
        # 4. 静态常数（法则与里程碑）持久化路径
        self.lore_file = self.workspace_dir / "lore_bounds.json"
        self.arcs_file = self.workspace_dir / "story_arcs.json"

    def initialize_world(self, raw_outline_path: str):
        """
        [编译期]：世界观初始化。
        具备完全的幂等性：如果有档则直接跳过，无档则拉起 Architect 执行强类型创世。
        """
        if self.state_tracker.state is not None:
            logger.info(f"💾 读档成功：世界状态已存在，将从第 {self.state_tracker.state.current_chapter_num} 章恢复运行。")
            return

        logger.warning("🌍 未检测到世界存档，引擎切换至创世模式...")
        
        if not os.path.exists(raw_outline_path):
            raise FileNotFoundError(f"🚨 致命错误：大纲源文件丢失 {raw_outline_path}")
            
        with open(raw_outline_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        # 拉起 Architect 降维大纲
        blueprint = self.architect.compile_world_blueprint(raw_text)

        # 剥离静态数据落盘（供 Critic 和 Assembler 使用）
        self.lore_file.write_text(
            blueprint.lore_bounds.model_dump_json(indent=2), 
            encoding='utf-8'
        )
        self.arcs_file.write_text(
            json.dumps([arc.model_dump() for arc in blueprint.arcs], indent=2, ensure_ascii=False), 
            encoding='utf-8'
        )

        # 剥离动态数据注入 Tracker
        self.state_tracker.initialize_state(blueprint.initial_state)
        logger.info("✅ 创世完毕：底层逻辑锁已扣合，里程碑坐标已锚定。")

    def _get_current_milestone(self) -> str:
        """
        [感知域]：自动提取当前卷宗的核心里程碑。
        指导 Actor 本章该往哪个方向推进，防止流水账。
        """
        try:
            arcs_data = json.loads(self.arcs_file.read_text(encoding='utf-8'))
            for arc in arcs_data:
                for milestone in arc.get("milestones", []):
                    # 发现第一个未完成的里程碑，直接返回作为当前战术目标
                    if not milestone.get("is_completed", False):
                        return f"所属卷宗：{arc['arc_name']}。核心战术目标：{milestone['description']}"
            return "所有预设里程碑已打通。请启动大结局收尾逻辑。"
        except Exception as e:
            logger.warning(f"里程碑感知系统故障，回退为自由演化模式: {e}")
            return "顺应当前局势，合理推进剧情。"

    def run_generation_loop(self, target_chapters: int):
        """
        [运行期]：核心黑盒自纠偏死循环。
        引擎将接管一切，直到达到 target_chapters 或触发无法修复的逻辑崩塌。
        """
        if not self.state_tracker.state:
            raise RuntimeError("🚨 引擎未初始化，请先执行 initialize_world()。")

        current_chapter = self.state_tracker.state.current_chapter_num
        logger.info(f"🚀 引擎推演启动。目标：{target_chapters} 章。当前刻度：{current_chapter}。")

        # 加载静态物理法则（贯穿全局）
        lore_json = self.lore_file.read_text(encoding='utf-8')

        while current_chapter < target_chapters:
            target_chapter_num = current_chapter + 1
            logger.info(f"\n{'='*15} [第 {target_chapter_num} 章推演开始] {'='*15}")
            
            try:
                # ==========================================
                # 1. 组装期 (Assembly Phase)
                # ==========================================
                current_state_json = self.state_tracker.get_context_for_prompt()
                milestone = self._get_current_milestone()
                
                logger.debug("正在动态组装上下文弹药...")
                assembled_prompts = self.assembler.assemble_payload(
                    lore_json=lore_json,
                    state_json=current_state_json,
                    current_milestone=milestone
                )
                
                # ==========================================
                # 2. Actor-Critic 自纠偏循环 (The Judgment Loop)
                # ==========================================
                attempt = 0
                max_rewrites = 3
                feedback: Optional[str] = None
                draft_approved = False
                final_draft = None
                
                while attempt < max_rewrites and not draft_approved:
                    # Actor：基于当前组装的弹药和可能的 feedback 生成草稿与补丁
                    draft = self.actor.generate_draft(assembled_prompts, feedback)
                    
                    # Critic：无情核对 Actor 的草稿是否违反了法则或当前状态
                    evaluation = self.critic.evaluate_draft(
                        draft_json=draft.model_dump_json(),
                        state_json=current_state_json,
                        lore_json=lore_json
                    )
                    
                    if evaluation.is_approved:
                        logger.info("⚖️ 审判庭裁决：逻辑闭环完好，通过。")
                        draft_approved = True
                        final_draft = draft
                    else:
                        attempt += 1
                        feedback = evaluation.correction_guidelines
                        logger.warning(f"❌ 审判庭驳回 (尝试 {attempt}/{max_rewrites}): {evaluation.violation_report}")
                        logger.warning(f"强制修正指令: {feedback}")

                # 熔断防御：大模型智力不足以破局，陷入死锁
                if not draft_approved:
                    logger.critical(f"🚨 引擎过载！在第 {target_chapter_num} 章陷入逻辑死锁。")
                    logger.critical("Actor 连续 3 次无法生成符合设定的剧情，为防止雪崩，引擎触发主动停机。")
                    raise RuntimeError("Actor-Critic 循环破裂。")
                
                # ==========================================
                # 3. 提交期 (Commit Phase - Two-Phase Commit)
                # ==========================================
                # 首先应用状态补丁，如果不合法，依然要抛出异常拒绝落盘
                patch_success = self.state_tracker.apply_patch(final_draft.state_patch.model_dump_json())
                if not patch_success:
                     raise RuntimeError("🚨 系统严重异常：Critic 误放行了非法的状态补丁！")
                
                # 状态机更新成功后，执行物理落盘
                chapter_file = self.workspace_dir / f"chapter_{str(target_chapter_num).zfill(3)}.txt"
                chapter_file.write_text(
                    f"# 第 {target_chapter_num} 章：{final_draft.chapter_title}\n\n{final_draft.content}", 
                    encoding='utf-8'
                )
                
                current_chapter += 1
                logger.info(f"💾 第 {target_chapter_num} 章落盘成功。进度推进。")
                
                # 强制冷却，防止 API 触发 HTTP 429 速率限制
                time.sleep(5) 
                
            except Exception as e:
                logger.error(f"💥 引擎在第 {current_chapter + 1} 章发生不可逆崩溃: {e}", exc_info=True)
                logger.warning("流水线强行终止。存档已安全锁定，修复后可无缝重启。")
                break
                
        if current_chapter >= target_chapters:
            logger.info("🎉 宏大推演结束。预设卷帙已全部生成，黑盒安全下线。")