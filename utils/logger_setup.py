import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(name: str, log_file: str = "logs/engine_run.log", level=logging.INFO) -> logging.Logger:
    """
    工业级日志生成器：专为长时间无人值守的流水线设计。
    支持控制台与文件的双写，并带有文件大小滚动截断机制。
    """
    # 1. 确保日志存储目录存在
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # 2. 初始化 Logger 实例
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 3. 避免在热重载或多次实例化时重复添加 Handler 导致日志刷屏
    if not logger.handlers:
        # --- 控制台输出端 (Console) ---
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        # 控制台注重整洁，显示时间、级别和模块名
        console_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s', 
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)

        # --- 文件持久化端 (File) ---
        # 开启日志滚动：每个文件最大 10MB，最多保留 5 个备份，强制 UTF-8 防止小说文本乱码
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setLevel(level)
        # 文件日志需要极度详细，精确到代码行号，方便系统崩溃后进行尸检
        file_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | [%(filename)s:%(lineno)d] | %(message)s'
        )
        file_handler.setFormatter(file_format)

        # 4. 挂载输出端
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger