import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# ==========================================
# 1. 数据字典定义 (Data Models)
# ==========================================

class Item(BaseModel):
    name: str = Field(..., description="物品名称")
    quantity: int = Field(default=1, ge=0, description="数量，不得为负")
    description: str = Field(..., description="一句话描述物品核心用途")

class Relationship(BaseModel):
    target_name: str = Field(..., description="交互对象名称")
    affection: int = Field(default=0, ge=-100, le=100, description="好感度(-100到100)")
    status: Literal["alive", "dead", "missing", "unknown"] = Field(default="alive")

class CharacterState(BaseModel):
    name: str
    current_location: str = Field(..., description="角色当前精确位置")
    power_level: str = Field(..., description="当前境界/战力等级")
    health_status: Literal["healthy", "injured", "dying", "dead"] = Field(default="healthy")
    inventory: List[Item] = Field(default_factory=list)
    relationships: Dict[str, Relationship] = Field(default_factory=dict)

class GlobalState(BaseModel):
    current_chapter_num: int = Field(default=0)
    world_timeline: str = Field(default="故事刚刚开始", description="当前世界的核心局势描述")
    protagonist: CharacterState
    key_npcs: Dict[str, CharacterState] = Field(default_factory=dict)
    recent_summaries: List[str] = Field(default_factory=list, description="滑动窗口：最近10章的硬摘要")

# ==========================================
# 2. 状态补丁定义 (用于接收大模型的更新指令)
# ==========================================

class StatePatch(BaseModel):
    """大模型在每章结尾必须输出的 JSON 格式"""
    new_location: Optional[str] = None
    health_change: Optional[Literal["healthy", "injured", "dying", "dead"]] = None
    items_acquired: List[Item] = Field(default_factory=list)
    items_lost: List[str] = Field(default_factory=list, description="丢失或消耗的物品名称")
    relationship_updates: List[Relationship] = Field(default_factory=list)
    chapter_summary: str = Field(..., description="本章的硬核摘要，限100字内，用于加入滑动窗口")
    timeline_update: Optional[str] = Field(None, description="如果世界局势发生重大变化，在此更新")

# ==========================================
# 3. 状态管理器引擎 (State Tracker)
# ==========================================

class StateTracker:
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.state_file = self.workspace / "story_state.json"
        self.backup_file = self.workspace / "story_state.json.bak"
        self.state: Optional[GlobalState] = None
        self._load_state()

    def _load_state(self):
        """带容错机制的状态加载"""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding='utf-8'))
                self.state = GlobalState(**data)
                logger.info(f"成功加载状态，当前进度：第 {self.state.current_chapter_num} 章")
                return
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"主状态文件损坏，尝试读取备份: {e}")
                if self.backup_file.exists():
                    data = json.loads(self.backup_file.read_text(encoding='utf-8'))
                    self.state = GlobalState(**data)
                    logger.info("已从备份文件恢复状态。")
                    return
                else:
                    raise RuntimeError("状态文件与备份文件均损坏，系统无法继续。")
        
        # 初始化空状态 (需由外部传入大纲数据进行初步填充)
        logger.warning("未找到状态文件，等待初始化。")

    def initialize_state(self, initial_state: GlobalState):
        """首次运行时的状态注入"""
        self.state = initial_state
        self._save_state()

    def _save_state(self):
        """原子写入与备份机制，防崩溃"""
        if not self.state:
            return
        
        # 1. 保存当前有效状态到备份文件
        if self.state_file.exists():
            self.backup_file.write_text(self.state_file.read_text(encoding='utf-8'), encoding='utf-8')
            
        # 2. 写入新状态
        json_str = self.state.model_dump_json(indent=2)
        
        # 使用临时文件写入，成功后再重命名，避免写入一半断电
        temp_file = self.workspace / "story_state.tmp"
        temp_file.write_text(json_str, encoding='utf-8')
        temp_file.replace(self.state_file)
        
    def apply_patch(self, patch_json_str: str) -> bool:
        """
        核心逻辑：解析大模型输出的补丁，并更新状态
        返回 True 表示更新成功，返回 False 表示补丁不合法，需要触发回滚或重试
        """
        try:
            # 1. 验证 JSON 补丁合法性
            patch_dict = json.loads(patch_json_str)
            patch = StatePatch(**patch_dict)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"大模型输出的状态补丁格式错误: {e}")
            return False

        # 2. 应用主角状态更新
        if patch.new_location:
            self.state.protagonist.current_location = patch.new_location
        if patch.health_change:
            self.state.protagonist.health_status = patch.health_change
            
        # 3. 物品增删逻辑 (严防凭空消耗)
        self.state.protagonist.inventory.extend(patch.items_acquired)
        
        current_item_names = [item.name for item in self.state.protagonist.inventory]
        for lost_item in patch.items_lost:
            if lost_item in current_item_names:
                # 简单实现：按名称剔除第一个匹配项。复杂情况可引入数量扣减逻辑
                idx = current_item_names.index(lost_item)
                self.state.protagonist.inventory.pop(idx)
                current_item_names.pop(idx)
            else:
                logger.warning(f"逻辑预警：尝试消耗不存在的物品 [{lost_item}]，已忽略。")

        # 4. 人物关系更新
        for rel in patch.relationship_updates:
            self.state.protagonist.relationships[rel.target_name] = rel

        # 5. 滑动窗口与世界观更新
        if patch.timeline_update:
            self.state.world_timeline = patch.timeline_update
            
        self.state.recent_summaries.append(patch.chapter_summary)
        if len(self.state.recent_summaries) > 10:
            self.state.recent_summaries.pop(0) # 维持最近 10 章的硬摘要

        self.state.current_chapter_num += 1
        
        # 6. 持久化
        self._save_state()
        logger.info(f"状态已更新至第 {self.state.current_chapter_num} 章。")
        return True

    def get_context_for_prompt(self) -> str:
        """提取紧凑的 JSON 字符串，供拼装下一章的 Prompt 使用"""
        if not self.state:
            return "{}"
        
        # 在组装 Prompt 时，不需要暴露太多的内部结构，提取精简版本
        context_dict = {
            "current_chapter": self.state.current_chapter_num + 1,
            "protagonist_status": {
                "location": self.state.protagonist.current_location,
                "power_level": self.state.protagonist.power_level,
                "health": self.state.protagonist.health_status,
                "inventory": [item.name for item in self.state.protagonist.inventory]
            },
            "recent_events": self.state.recent_summaries[-3:], # 只喂给大模型最近3章摘要防止污染
            "world_timeline": self.state.world_timeline
        }
        return json.dumps(context_dict, ensure_ascii=False, indent=2)