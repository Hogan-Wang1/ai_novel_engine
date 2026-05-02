import os
import sys
import json
import logging
import subprocess

# 【优先级最高：秘钥加电】
# 必须在导入其他本地组件前执行，防止它们在顶层 import 时抓取不到环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("🛑 致命错误: 未安装 python-dotenv。请运行 pip install python-dotenv")
    sys.exit(1)

# === 引入系统各层级组件 ===
from utils.logger_setup import setup_logger
from clients.robust_caller import RobustCaller
from memory.vector_db_client import VectorDBClient
from memory.state_tracker import StateTracker
from memory.recap_manager import RecapManager

from engine.context_assembler import ContextAssembler
from engine.generator_chapter import ChapterGenerator
from engine.plot_enforcer import PlotEnforcer  # 修正了之前的 plot_evolver 错字
from engine.generator_architect import OutlineArchitect
from engine.orchestrator import NovelOrchestrator

def bootstrap_system():
    """依赖注入与系统初始化拓扑 (IoC Container)"""
    # 1. 启动工业级日志 (双写：控制台 + 文件)
    load_dotenv()
    logger = setup_logger("Engine-CoPilot")
    llm_client = RobustCaller(model_name="deepseek-chat") 

    config_path = "config/run_config.yaml"
    workspace_dir = "./output/workspaces"
    os.makedirs(workspace_dir, exist_ok=True)

    try:
        # 2. 初始化底层基建 (Infrastructure Layer)
        logger.info("🔧 正在挂载通信与记忆基建 (LLM, VectorDB, StateTracker)...")
        llm_client = RobustCaller(model_name="gpt-4o") 
        vector_db = VectorDBClient(db_path="./.chroma_db")
        state_tracker = StateTracker(workspace_dir)
        recap_manager = RecapManager(vector_db, workspace_dir)

        # 3. 读取创世配置，初始化引擎核心组件 (Engine Core Layer)
        logger.info("⚙️ 正在装载黑盒引擎核心驱动...")
        assembler = ContextAssembler(config_path, state_tracker, recap_manager, vector_db)
        
        # 将配置传递给大纲架构师
        config_data = assembler.config 
        architect = OutlineArchitect(llm_client, config_data)
        
        generator = ChapterGenerator(llm_client)
        enforcer = PlotEnforcer(llm_client)

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
        logger.critical(f"🛑 系统加电失败，依赖注入链条断裂: {str(e)}")
        sys.exit(1)

def ensure_outline(architect: OutlineArchitect, workspace_dir: str, logger: logging.Logger) -> list:
    """获取或生成初始大纲（卷级动态控制）"""
    outline_path = os.path.join(workspace_dir, "current_volume_outline.json")
    
    # 断点续传支持：如果大纲已存在，直接读取内存
    if os.path.exists(outline_path):
        logger.info("📂 检测到已存在的卷级大纲，正在读取内存...")
        try:
            with open(outline_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ 大纲文件读取失败: {str(e)}。准备重新生成...")
            
    # 冷启动：首次生成第一卷大纲
    logger.info("✨ 冷启动：正在推演第一卷 (Volume 1) 高致密大纲...")
    volume_outline = architect.generate_volume_outline(volume_number=1) 
    
    if not volume_outline:
        logger.critical("🛑 大纲推演失败，无法获取世界坐标，系统停机。")
        sys.exit(1)
        
    with open(outline_path, "w", encoding="utf-8") as f:
        json.dump(volume_outline, f, ensure_ascii=False, indent=2)
        
    logger.info("✅ 第一卷大纲锚定完毕，已持久化落盘。")
    return volume_outline

def run_headless_engine():
    """纯后台无头模式：执行真正的黑盒叙事管线"""
    architect, orchestrator, workspace_dir, logger = bootstrap_system()
    volume_outline = ensure_outline(architect, workspace_dir, logger)

    logger.info("==================================================")
    logger.info("🚀 无头模式点火！后台流水线全面接管控制权。")
    logger.info("==================================================")
    
    try:
        orchestrator.run_pipeline(full_outline=volume_outline)
    except KeyboardInterrupt:
        logger.warning("\n⚠️ 侦测到人工干预 (Ctrl+C)，系统正在安全停机并封存断点...")
    except Exception as e:
        logger.critical(f"💥 发生致命异常，主引擎循环崩溃: {str(e)}")
    finally:
        logger.info("💤 引擎守护进程已关闭。")

if __name__ == "__main__":
    # 【智能路由中枢】
    if "--headless" in sys.argv:
        # 1. 守护进程分支：由 UI 面板在后台触发
        run_headless_engine()
    else:
        # 2. 前端进程分支：用户在终端直接执行 python main.py
        print("🌌 AI Novel Engine: 正在唤醒创世控制台 (Streamlit UI)...")
        print("💡 提示: 如果浏览器未自动弹出，请手动复制下方 Local URL。")
        
        python_exe = sys.executable 
        try:
            # 自动拉起 ui_dashboard.py
            subprocess.run([python_exe, "-m", "streamlit", "run", "ui_dashboard.py"])
        except KeyboardInterrupt:
            print("\n💤 创世控制台已安全关闭。")
        except Exception as e:
            print(f"❌ UI 面板拉起失败: {str(e)}")