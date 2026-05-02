import os
import json
import logging
import sys

# === 引入系统各层级组件 ===
from utils.logger_setup import setup_logger
from clients.robust_caller import RobustCaller
from memory.vector_db_client import VectorDBClient
from memory.state_tracker import StateTracker
from memory.recap_manager import RecapManager

from engine.context_assembler import ContextAssembler
from engine.generator_chapter import ChapterGenerator
from engine.plot_evolver import PlotEnforcer
from engine.orchestrator import NovelOrchestrator

# (假设你有一个专门生成大纲的类，如果没有，可以通过 RobustCaller 在此处写一个简易版)
from engine.generator_architect import OutlineArchitect 

def bootstrap_system():
    """依赖注入与系统初始化拓扑"""
    # 1. 启动工业级日志 (双写：控制台 + 文件)
    logger = setup_logger("Engine-CoPilot", log_file="logs/engine_run.log", level=logging.INFO)
    logger.info("🌌 AI Novel Engine: 系统正在加电...")

    config_path = "config/run_config.yaml"
    workspace_dir = "./output/workspaces"
    os.makedirs(workspace_dir, exist_ok=True)

    try:
        # 2. 初始化底层基建 (Infrastructure Layer)
        logger.info("🔧 正在挂载底层基建 (LLM, 向量库, 状态追踪器)...")
        llm_client = RobustCaller(model_name="gpt-4o") # 替换为你的大模型路由配置
        vector_db = VectorDBClient(db_path="./.chroma_db")
        state_tracker = StateTracker(workspace_dir)
        recap_manager = RecapManager(vector_db, workspace_dir)

        # 3. 初始化引擎核心组件 (Engine Core Layer)
        logger.info("⚙️ 正在装载黑盒引擎核心逻辑...")
        assembler = ContextAssembler(config_path, state_tracker, recap_manager, vector_db)
        generator = ChapterGenerator(llm_client)
        enforcer = PlotEnforcer(llm_client)
        architect = OutlineArchitect(llm_client, config_path)

        # 4. 组装最高指挥中枢 (Orchestrator)
        logger.info("🧠 正在唤醒最高指挥中枢 (Orchestrator)...")
        orchestrator = NovelOrchestrator(
            config_path=config_path,
            assembler=assembler,
            generator=generator,
            enforcer=enforcer,
            state_tracker=state_tracker,
            recap_manager=recap_manager,
            output_dir=workspace_dir
        )
        
        return architect, orchestrator, workspace_dir, logger

    except Exception as e:
        logger.critical(f"🛑 系统加电失败，依赖注入崩溃: {str(e)}")
        sys.exit(1)

def ensure_outline(architect: OutlineArchitect, workspace_dir: str, logger: logging.Logger) -> list:
    """获取或生成初始大纲（卷级控制）"""
    outline_path = os.path.join(workspace_dir, "current_volume_outline.json")
    
    # 支持断点续传：如果大纲已存在，直接读取
    if os.path.exists(outline_path):
        logger.info("📂 检测到已存在的卷级大纲，正在读取内存...")
        with open(outline_path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    # 冷启动：首次生成第一卷大纲
    logger.info("✨ 冷启动：正在生成第一卷 (Volume 1) 高致密大纲...")
    # 这里调用 architect 生成，假设返回一个包含章节字典的 List
    volume_outline = architect.generate_volume_outline(volume_number=1) 
    
    if not volume_outline:
        logger.critical("🛑 大纲生成失败，无法获取世界坐标。")
        sys.exit(1)
        
    with open(outline_path, "w", encoding="utf-8") as f:
        json.dump(volume_outline, f, ensure_ascii=False, indent=2)
        
    logger.info("✅ 第一卷大纲锚定完毕，已落盘。")
    return volume_outline

def main():
    # === 阶段 1：系统加电与装载 ===
    architect, orchestrator, workspace_dir, logger = bootstrap_system()

    # === 阶段 2：世界观锚定 (生成第一卷细纲) ===
    volume_outline = ensure_outline(architect, workspace_dir, logger)

    # === 阶段 3：引擎点火，进入无人值守状态 ===
    logger.info("==================================================")
    logger.info("🚀 创世大爆炸完成！流水线全面接管控制权。")
    logger.info("==================================================")
    
    try:
        # 移交控制权给死循环心跳总线
        orchestrator.run_pipeline(full_outline=volume_outline)
    except KeyboardInterrupt:
        logger.warning("\n⚠️ 侦测到人工干预 (Ctrl+C)，系统正在安全停机并保存断点...")
    except Exception as e:
        logger.critical(f"💥 发生未捕获的致命异常，系统崩溃: {str(e)}")
        # 实际生产中可在此处添加邮件/飞书/钉钉报警钩子
    finally:
        logger.info("💤 引擎已进入休眠状态。")

if __name__ == "__main__":
    main()