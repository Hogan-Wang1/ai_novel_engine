from typing import Dict
import json

class RecapManager:
    """自动记忆评估器：决定什么该进入长线记忆"""
    
    @staticmethod
    def identify_milestone(thought_process: str, state_updates: Dict) -> bool:
        """
        基于 Orchestrator 输出的 JSON 自动判定：
        如果涉及角色死亡、重大物品获得、地点转移，则标记为里程碑。
        """
        # 逻辑判定锁：如果 dead_characters 不为空，必为里程碑
        if state_updates.get("dead_characters"):
            return True
        
        # 如果当前动机（motive）发生剧变，标记为里程碑
        for char in state_updates.get("character_updates", []):
            if "突破" in char.get("status", "") or "获得" in char.get("current_motive", ""):
                return True
                
        return False