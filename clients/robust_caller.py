import json
import re
import logging
from typing import Type, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)

logger = logging.getLogger(__name__)

# 定义泛型，用于 Pydantic 模型的类型推导
T = TypeVar('T', bound=BaseModel)

class LLMFatalError(Exception):
    """当所有重试和降级策略都失败时抛出的致命异常"""
    pass

class RobustCaller:
    """
    工业级大模型调用网关
    具备：格式自愈、指数退避重试、多模型降级熔断功能
    """
    def __init__(self, primary_client_func, fallback_client_func=None):
        """
        :param primary_client_func: 主模型的调用函数 (签名需为: func(messages: list) -> str)
        :param fallback_client_func: 备用模型的调用函数
        """
        self.primary_client_func = primary_client_func
        self.fallback_client_func = fallback_client_func

    def _extract_json(self, raw_response: str) -> str:
        """残骸剥离：暴力清洗大模型输出的 Markdown 标记或多余文本"""
        # 尝试匹配 ```json ... ``` 或 ``` ... ``` 之间的内容
        match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', raw_response, re.DOTALL)
        if match:
            return match.group(1)
        
        # 如果没有 markdown 标记，尝试寻找第一个 '{' 和最后一个 '}'
        start_idx = raw_response.find('{')
        end_idx = raw_response.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            return raw_response[start_idx:end_idx+1]
            
        return raw_response # 如果都找不到，原样返回碰碰运气

    def _invoke_with_fallback(self, messages: List[Dict[str, str]]) -> str:
        """带降级策略的基础网络调用，处理 502/429 等网络层异常"""
        
        # 使用 Tenacity 处理瞬时网络故障（指数退避：等 2, 4, 8 秒...）
        @retry(
            wait=wait_exponential(multiplier=1, min=2, max=10),
            stop=stop_after_attempt(3),
            reraise=True
        )
        def _call_primary():
            logger.debug("正在请求主模型...")
            return self.primary_client_func(messages)

        try:
            return _call_primary()
        except Exception as e:
            logger.warning(f"主模型调用失败 (已重试3次): {e}")
            if self.fallback_client_func:
                logger.warning("触发熔断机制，正在切换至备用模型...")
                try:
                    return self.fallback_client_func(messages)
                except Exception as fallback_e:
                    logger.error(f"备用模型亦调用失败: {fallback_e}")
                    raise LLMFatalError("所有可用模型均无响应，网络层彻底崩溃。") from fallback_e
            else:
                raise LLMFatalError("主模型崩溃且未配置备用模型。") from e

    def ask_for_structured_data(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        response_model: Type[T], 
        max_repairs: int = 3
    ) -> T:
        """
        核心防爆函数：强制要求大模型返回符合 Pydantic 定义的 JSON 数据。
        如果解析失败，会携带报错信息重新请求大模型进行自我修复。
        """
        # 自动将 Pydantic 模型的结构转换为提示词，强制约束 LLM
        schema_json = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        
        injected_system = (
            f"{system_prompt}\n\n"
            f"【最高指令 - 严格格式约束】\n"
            f"你必须且只能返回合法的 JSON 格式数据。绝不能包含任何额外的解释文字、思考过程或 Markdown 代码块符。\n"
            f"你的输出必须严格符合以下 JSON Schema 定义：\n"
            f"{schema_json}"
        )

        messages = [
            {"role": "system", "content": injected_system},
            {"role": "user", "content": user_prompt}
        ]

        attempt = 0
        last_error = ""

        while attempt <= max_repairs:
            if attempt > 0:
                logger.warning(f"启动自我修复机制 (Attempt {attempt}/{max_repairs})")
                # 核心逻辑：将上一次的解析错误塞回给大模型
                repair_prompt = (
                    f"你上一次的输出解析失败了。错误信息如下：\n{last_error}\n"
                    f"请修正格式错误，并重新输出符合要求的纯 JSON。"
                )
                messages.append({"role": "user", "content": repair_prompt})

            raw_response = self._invoke_with_fallback(messages)
            cleaned_json = self._extract_json(raw_response)

            try:
                # 1. 尝试 JSON 解码
                data_dict = json.loads(cleaned_json)
                
                # 2. 尝试 Pydantic 业务逻辑与类型校验
                validated_data = response_model(**data_dict)
                
                if attempt > 0:
                    logger.info("格式自我修复成功！")
                
                return validated_data

            except json.JSONDecodeError as e:
                last_error = f"JSON格式错误 (JSONDecodeError): {e}。你输出的字符串是: {cleaned_json}"
                logger.error(f"LLM 输出了无效的 JSON。")
            except ValidationError as e:
                last_error = f"数据字段校验不通过 (Pydantic ValidationError): {e}"
                logger.error(f"LLM 输出了缺少字段或类型错误的 JSON。")
            
            # 将错误输出加入对话历史，防止上下文丢失
            messages.append({"role": "assistant", "content": raw_response})
            attempt += 1

        # 如果穷尽了修复次数依然失败，抛出致命异常中断流程（交由最外层捕获记录）
        logger.error("超出最大自我修复次数，当前节点彻底崩坏。")
        raise LLMFatalError(f"大模型未能输出合法的 JSON 结构，最后的错误: {last_error}")