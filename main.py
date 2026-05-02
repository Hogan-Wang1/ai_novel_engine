import os
import sys
import yaml
import logging
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import httpx
from openai import OpenAI
import warnings

# ---------------------------------------------------------
# 1. 运行时噪音抑制
# ---------------------------------------------------------
# 抑制由于 verify=False 导致的 InsecureRequestWarning，确保长篇生成日志的纯净
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# 引入核心组件 (确保 Phase 1-4 的文件在对应目录下)
from utils.logger_setup import setup_logger
from clients.robust_caller import RobustCaller
from engine.orchestrator import Orchestrator

# ---------------------------------------------------------
# 2. 大模型 API 适配器 (全兼容自适应版)
# ---------------------------------------------------------

def create_deepseek_client(api_key: str):
    """
    闭包工厂：标准化 DeepSeek API 适配器。
    
    【核心架构改动】
    - trust_env=True: 允许 httpx 自动寻找并使用 VPN 的系统代理 (解决 getaddrinfo 问题)。
    - verify=False: 彻底绕过 VPN 开启时因解包 HTTPS 导致的 SSL 协议违约报错。
    """
    # 强制默认指向 DeepSeek 标准路由
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    
    # 构造具备 VPN 兼容性的 HTTP 客户端
    # 注意：不再使用 proxy=None，让其自动跟随系统环境
    custom_http_client = httpx.Client(
        trust_env=True,  
        timeout=httpx.Timeout(connect=20.0, read=180.0, write=20.0, pool=20.0),
        verify=False     # 核心修复点：绕过 SSL EOF 错误[cite: 3]
    )

    client = OpenAI(
        api_key=api_key, 
        base_url=base_url,
        http_client=custom_http_client
    )
    
    def call_llm(messages: list) -> str:
        model_name = os.getenv("LLM_MODEL", "deepseek-chat")
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.8, 
            max_tokens=4096  
        )
        return response.choices[0].message.content
        
    return call_llm

# ---------------------------------------------------------
# 3. 环境变量与安全自检
# ---------------------------------------------------------

def _check_env_and_get_key(logger: logging.Logger) -> str:
    """自动加载 .env 并校验 API Key，防止硬编码泄露至 GitHub"""
    dotenv_path = find_dotenv()
    if dotenv_path:
        load_dotenv(dotenv_path, override=True)
        logger.info(f"已成功识别并加载环境变量配置: {dotenv_path}")
    else:
        logger.warning("未在根目录发现 .env 文件，将尝试读取系统环境变量。")

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        logger.critical("-" * 40)
        logger.critical("🚨 致命错误：缺失 LLM_API_KEY！")
        logger.critical("请将 .env.example 复制为 .env 并填入你的 DeepSeek Key。")
        logger.critical("-" * 40)
        sys.exit(1)
    return api_key

def main():
    # 1. 引擎日志初始化
    logger = setup_logger(name="NovelEngine", log_file="data/workspaces/engine_run.log")
    logger.info("============== 黑盒叙事引擎 (Engine-CoPilot) 启动 ==============")

    try:
        # 2. 安全鉴权
        api_key = _check_env_and_get_key(logger)

        # 3. 参数配置加载
        config_path = "run_config.yaml"
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        else:
            config = {}

        workspace_dir = config.get("workspace_dir", "./data/workspaces/project_alpha")
        outline_path = config.get("outline_path", "./data/my_outline.txt")
        target_chapters = config.get("target_chapters", 100)

        # 4. 依赖注入：装配具备 VPN 穿透能力的内核
        logger.info("正在装配 DeepSeek 引擎内核 (自适应代理模式)...")
        primary_llm_func = create_deepseek_client(api_key)
        
        caller = RobustCaller(primary_client_func=primary_llm_func)
        orchestrator = Orchestrator(workspace_dir=workspace_dir, caller=caller)

        # 5. 执行创世或读档
        if not os.path.exists(outline_path):
            logger.warning(f"大纲文件 {outline_path} 缺失，已自动补全演示大纲。")
            os.makedirs(os.path.dirname(outline_path), exist_ok=True)
            with open(outline_path, "w", encoding="utf-8") as f:
                f.write("主角林凡，练气期开局，立志飞升。战力：练气、筑基、金丹。绝对法则：禁止跨级杀敌。")

        # [黑盒核心] 初始化世界与调度生成循环
        orchestrator.initialize_world(raw_outline_path=outline_path)
        
        logger.info(f"点火完成。目标卷帙: {target_chapters} 章。切入全自动无人值守模式...")
        orchestrator.run_generation_loop(target_chapters=target_chapters)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 接收到人工中断指令，正在保存当前剧情状态快照...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"🔥 发生无法自愈的致命异常，进程崩溃: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("============== 引擎运行生命周期结束 ==============")

if __name__ == "__main__":
    main()