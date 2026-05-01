import os
import json
from typing import Type, TypeVar, Optional
from openai import AsyncOpenAI, APIConnectionError, RateLimitError
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from loguru import logger
import logging

# 泛型定义，用于 Pydantic 强校验返回
T = TypeVar('T', bound=BaseModel)

class DeepSeekRouter:
    """
    黑盒叙事引擎：大模型通信枢纽与异常熔断器
    """
    def __init__(self):
        # 1. 初始化鉴权与基建环境变量
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        
        if not self.api_key:
            logger.error("点火失败: DEEPSEEK_API_KEY 环境变量未设置！")
            raise ValueError("Missing DEEPSEEK_API_KEY")

        # 2. 实例化异步 OpenAI 客户端
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=float(os.getenv("API_TIMEOUT_SECONDS", 120.0))
        )
        
        # 3. 路由配置 (根据任务特性分发模型)
        self.reasoning_model = os.getenv("LLM_MODEL_REASONING", "deepseek-reasoner")
        self.generation_model = os.getenv("LLM_MODEL_GENERATION", "deepseek-chat")

    # ==========================================
    # 工业级装饰器：自动重试与指数退避
    # ==========================================
    @retry(
        # 遇到网络错误或限流时重试，如果是鉴权错误(API Key错)则直接崩溃
        retry=retry_if_exception_type((APIConnectionError, RateLimitError, ValidationError, json.JSONDecodeError)),
        stop=stop_after_attempt(int(os.getenv("MAX_RETRIES", 5))),
        wait=wait_exponential(
            multiplier=int(os.getenv("RETRY_BACKOFF_FACTOR", 2)), 
            min=4, 
            max=int(os.getenv("RETRY_MAX_DELAY", 60))
        ),
        before_sleep=lambda retry_state: logger.warning(
            f"API 调用受阻或结构化解析失败，准备第 {retry_state.attempt_number} 次重试. "
            f"异常: {retry_state.outcome.exception()}"
        )
    )
    async def generate_structured_data(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        response_model: Type[T], 
        temperature: float = 0.3
    ) -> T:
        """
        强校验输出层：专门用于大纲生成、状态机检查、逻辑锁（必须输出完美 JSON）
        """
        logger.info(f"路由请求至逻辑模型: {self.reasoning_model} (温度: {temperature})")
        
        # 强制在系统提示词中注入 JSON 格式要求，避免模型跑偏
        json_enforcement = (
            f"\n\nCRITICAL INSTRUCTION: You MUST output ONLY valid JSON. "
            f"The JSON must strictly adhere to the following schema:\n{response_model.model_json_schema()}"
        )
        
        response = await self.client.chat.completions.create(
            model=self.reasoning_model,
            messages=[
                {"role": "system", "content": system_prompt + json_enforcement},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            response_format={"type": "json_object"} # 强制 DeepSeek 返回 JSON 模式
        )
        
        raw_content = response.choices[0].message.content
        
        # 提取、解析并使用 Pydantic 进行业务级别的强校验
        # 任何 OOC 或缺失字段都会触发 ValidationError，从而被 @retry 捕获重新生成
        parsed_data = response_model.model_validate_json(raw_content)
        return parsed_data

    @retry(
        retry=retry_if_exception_type((APIConnectionError, RateLimitError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        before_sleep=lambda retry_state: logger.warning(f"正文生成流中断，重试中... 异常: {retry_state.outcome.exception()}")
    )
    async def generate_chapter_text(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.85
    ) -> str:
        """
        高并发正文流：专门用于百万字正文的铺陈（更具文学性和多样性）
        """
        logger.info(f"路由请求至生成模型: {self.generation_model} (温度: {temperature})")
        
        response = await self.client.chat.completions.create(
            model=self.generation_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=int(os.getenv("MAX_TOKENS_CHAPTER", 4000))
        )
        
        return response.choices[0].message.content