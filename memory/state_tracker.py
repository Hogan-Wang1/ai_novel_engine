import os
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger("Engine-CoPilot.StateTracker")

class StateTracker:
    """
    RPG 级热记忆状态追踪器。
    负责维护角色的绝对物理状态、战力境界和核心装备，防止大模型发生“复活”或“战力膨胀”幻觉。
    """
    def __init__(self, workspace_dir: str):
        self.state_file = os.path.join(workspace_dir, "entities_state.json")
        # state 的数据结构约定: {"林风": {"status": "重伤", "power_level": "筑基", "inventory": ["神秘铁剑"]}}
        self.state: Dict[str, Dict[str, Any]] = self._load_state()
        logger.info("🛡️ 热记忆状态追踪器挂载成功。")

    def _load_state(self) -> Dict[str, Dict[str, Any]]:
        """从本地断点加载状态，确保断电重启后角色状态不丢失"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"❌ 状态文件损坏，将初始化为空状态: {str(e)}")
        return {}

    def _save_state(self):
        """将当前内存状态落盘为强类型的 JSON"""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 无法持久化角色状态: {str(e)}")

    def get_entities_snapshot(self, entity_names: List[str]) -> str:
        """
        向生成器 (Generator) 提供指定角色的实时状态面板。
        这是 ContextAssembler 的核心数据源。
        """
        if not self.state or not entity_names:
            return "当前无活动角色的特殊状态记录 (处于默认健康状态)。"

        snapshot = []
        for name in entity_names:
            if name in self.state:
                state_str = json.dumps(self.state[name], ensure_ascii=False)
                snapshot.append(f"【{name} 当前状态】: {state_str}")

        if not snapshot:
            return "提及的角色目前处于默认健康状态，无特殊 Debuff 或关键道具约束。"
        
        return "\n".join(snapshot)

    def get_current_snapshot_str(self) -> str:
        """
        向裁决者 (Critic/Enforcer) 提供全量状态，用于审查大模型是否发生 OOC 或设定崩塌。
        """
        if not self.state:
            return "全局状态：未记录任何角色异常。"
        return json.dumps(self.state, ensure_ascii=False, indent=2)

    def update_entities_from_text(self, chapter_text: str):
        """
        【架构预留接口】
        在完整的百万字流水线中，此函数会被 Orchestrator 呼叫。
        它应该调用 LLM (携带 RPG 数据库管理员 Prompt)，分析 chapter_text 中的受伤/死亡/获得物品事件，
        生成 JSON Diff 并通过 apply_state_diff 写入内存。
        目前作为桩函数 (Stub)，保证启动拓扑不报错。
        """
        # 预留给未来的 LLM 状态抽取器
        # logger.debug("正在扫描本章状态变更...")
        pass
        
    def apply_state_diff(self, state_diff: Dict[str, Dict[str, Any]]):
        """接收结构化的状态更新并落盘"""
        for entity, updates in state_diff.items():
            if entity not in self.state:
                self.state[entity] = {}
            # 增量更新角色属性
            self.state[entity].update(updates)
        self._save_state()
        logger.debug("🔄 角色热记忆状态已更新并持久化。")