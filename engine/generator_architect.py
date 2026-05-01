import re
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger("Engine-PromptArchitect")

class PromptArchitect:
    """
    提示词架构师：负责将静态设定、角色协议、动态状态和历史记忆编译成最终的 LLM 指令。
    """
    def __init__(
        self, 
        super_prompt_path: str = "prompts/super_prompt.md", 
        system_prompts_path: str = "config/prompts_template/system_prompts.yaml"
    ):
        self.super_prompt_raw = self._load_text(super_prompt_path)
        self.agent_templates = self._load_yaml(system_prompts_path)
        
        # 预编译核心区块
        self.global_constants = self._extract_section("GLOBAL_CONSTANTS")
        self.system_protocol = self._extract_section("SYSTEM_PROTOCOL")
        self.encyclopedia = self._parse_encyclopedia()

    def _load_text(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            logger.error(f"❌ 关键文件缺失: {path}")
            raise FileNotFoundError(path)
        return p.read_text(encoding="utf-8")

    def _load_yaml(self, path: str) -> Dict:
        p = Path(path)
        actual_path = p if p.exists() else Path(f"{path}.example") # 兼容 example
        with open(actual_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _extract_section(self, section_name: str) -> str:
        """正则提取 [SECTION: NAME] 区块"""
        pattern = rf"# \[SECTION: {section_name}\](.*?)(?=# \[SECTION:|$)"
        match = re.search(pattern, self.super_prompt_raw, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _parse_encyclopedia(self) -> Dict[str, str]:
        """解析百科全书条目 [ENTRY: KEY]"""
        encyclopedia_text = self._extract_section("ENCYCLOPEDIA")
        entries = {}
        pattern = r"## \[ENTRY: (.*?)\](.*?)(?=## \[ENTRY:|$)"
        matches = re.finditer(pattern, encyclopedia_text, re.DOTALL)
        for match in matches:
            entries[match.group(1).strip()] = match.group(2).strip()
        return entries

    def build_system_prompt(self, agent_role: str = "writer_agent") -> str:
        """
        构建带有“思想钢印”的系统提示词。
        整合：角色定义 + 全局法则 + 状态机同步协议[cite: 1]。
        """
        role_config = self.agent_templates.get(agent_role, {})
        constraints = "\n".join([f"- {c}" for c in role_config.get("constraints", [])])
        
        return f"""
# ROLE_IDENTITY
你是 {role_config.get('role', 'Engine-CoPilot')}。你的存在是为了执行高精度的叙事推演。

# GLOBAL_WORLD_LAWS
{self.global_constants}

# SYSTEM_OPERATIONAL_PROTOCOL
{self.system_protocol}

# SPECIFIC_CONSTRAINTS
{constraints}
{role_config.get('format_instruction', '')}
        """.strip()

    def build_user_prompt(
        self, 
        chapter_index: int, 
        current_state: Dict[str, Any], 
        plot_instruction: Dict[str, Any],
        prev_summary: str, 
        prev_hook: str,
        retrieved_memories: List[str]
    ) -> str:
        """
        动态编译用户提示词，实现“按需加载”知识。
        """
        # 1. 自动根据当前状态召回百科知识[cite: 1]
        state_str = json.dumps(current_state, ensure_ascii=False)
        relevant_entries = []
        for key, content in self.encyclopedia.items():
            # 如果当前位置或涉及角色在百科中，则注入
            if key in state_str or key in json.dumps(plot_instruction):
                relevant_entries.append(f"<{key}>\n{content}\n</{key}>")

        # 2. 组装任务包
        return f"""
<Task_Context>
当前进度：第 {chapter_index} 章
剧情指令：{json.dumps(plot_instruction, ensure_ascii=False)}
</Task_Context>

<Relevant_Encyclopedia>
{chr(10).join(relevant_entries) if relevant_entries else "无特定关联设定。"}
</Relevant_Encyclopedia>

<Long_Term_Memories>
{chr(10).join(retrieved_memories)}
</Long_Term_Memories>

<Current_State_Snapshot>
{state_str}
</Current_State_Snapshot>

<Preceding_Anchor>
【前章梗概】：{prev_summary}
【接续锚点】(正文第一句必须严密衔接此物理动作)："{prev_hook}"
</Preceding_Anchor>

请执行演算，并严格按照 JSON 协议输出本章结果。
""".strip()