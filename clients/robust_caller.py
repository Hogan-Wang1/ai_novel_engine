import os
import time
import logging
from typing import List, Dict, Any, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger("Engine-CoPilot.RobustCaller")

class RobustCaller:
    """
    工业级大模型 API 路由与调用装甲。
    专为无人值守的百万字流水线设计，包含指数退避与并发限流保护机制。
    """
    def __init__(self, model_name: str = "gpt-4o", base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.model_name = model_name
        
        # 优先读取传入的参数，否则尝试穿透读取环境变量
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        
        if not OpenAI:
            logger.critical("🛑 未检测到底层 openai 核心库，引擎即将瘫痪！请运行: pip install openai")
            raise ImportError("Missing required package: openai")
            
        if not self.api_key:
            logger.warning("⚠️ 警告：未检测到 API Key。请确保在 .env 文件中配置了 OPENAI_API_KEY。")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def call(self, messages: List[Dict[str, str]], temperature: float = 0.7, response_format: Optional[Dict[str, str]] = None, max_retries: int = 5) -> str:
        """
        带有自愈合逻辑的调用总线
        """
        base_wait_time = 2  # 基础避退秒数

        for attempt in range(1, max_retries + 1):
            try:
                kwargs: Dict[str, Any] = {
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": temperature,
                }
                
                # 强行锁定 JSON 输出格式（若 API 支持）
                if response_format:
                    kwargs["response_format"] = response_format

                response = self.client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""

            except Exception as e:
                error_msg = str(e)
                is_rate_limit = "429" in error_msg or "RateLimit" in error_msg or "Too Many Requests" in error_msg
                
                # 如果到达最大重试次数，触发系统级熔断
                if attempt == max_retries:
                    logger.critical(f"🛑 API 装甲被彻底击穿 (已尝试 {max_retries} 次)。最终错误: {error_msg}")
                    raise e
                    
                # 计算指数退避时间: 2, 4, 8, 16... 秒
                wait_time = base_wait_time * (2 ** (attempt - 1))
                
                # 针对高频限流的额外延迟惩罚
                if is_rate_limit:
                    wait_time += 15 

                logger.warning(f"⚠️ API 遭遇乱流 (尝试 {attempt}/{max_retries}) | 启动自愈，将在 {wait_time} 秒后重试 | 原因: {error_msg[:100]}")
                time.sleep(wait_time)
        
        return ""