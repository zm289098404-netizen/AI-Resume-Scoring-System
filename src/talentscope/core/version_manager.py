"""
Phase 3: 评分引擎版本管理系统
===============================

提供版本管理功能，支持：
- 多个评分算法版本注册和管理
- 版本的激活、查询、导出
- 版本历史跟踪
- 版本配置验证

使用示例：
    from talentscope.core.version_manager import VersionManager
    
    # 注册新版本
    VersionManager.register_version(
        version_id="v2.0",
        config={"skill_weight": 0.4, "experience_weight": 0.6},
        description="improved skill matching algorithm"
    )
    
    # 激活版本
    VersionManager.switch_version("v2.0")
    
    # 获取当前版本
    current = VersionManager.get_active_version()
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List


class ScoringEngineVersion:
    """单个评分引擎版本的定义和元数据"""
    
    def __init__(
        self,
        version_id: str,
        algorithm_config: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        初始化版本
        
        Args:
            version_id: 版本标识 (如 "v1", "v2.0", "v2_improved")
            algorithm_config: 评分算法配置 (权重、参数等)
            metadata: 元数据 (作者、描述、创建时间等)
        """
        self.version_id = version_id
        self.algorithm_config = algorithm_config
        self.metadata = metadata or {}
        
        # 自动添加系统字段
        if "created_at" not in self.metadata:
            self.metadata["created_at"] = datetime.now().isoformat()
        if "version_uuid" not in self.metadata:
            self.metadata["version_uuid"] = str(uuid.uuid4())
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        验证版本配置是否有效
        
        Returns:
            (is_valid, error_message)
        """
        # 验证 version_id
        if not isinstance(self.version_id, str) or not self.version_id.strip():
            return False, "version_id 不能为空"
        
        # 验证 algorithm_config
        if not isinstance(self.algorithm_config, dict):
            return False, "algorithm_config 必须是字典"
        
        # 验证权重字段 (如果存在)
        weight_fields = [k for k in self.algorithm_config.keys() if "weight" in k]
        for field in weight_fields:
            value = self.algorithm_config[field]
            if not isinstance(value, (int, float)):
                return False, f"{field} 必须是数字"
            if not (0 <= value <= 1):
                return False, f"{field} 必须在 0-1 之间"
        
        return True, None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "version_id": self.version_id,
            "algorithm_config": self.algorithm_config,
            "metadata": self.metadata
        }
    
    @staticmethod
    def from_dict(data: dict) -> "ScoringEngineVersion":
        """从字典创建版本"""
        return ScoringEngineVersion(
            version_id=data["version_id"],
            algorithm_config=data["algorithm_config"],
            metadata=data.get("metadata", {})
        )


class VersionManager:
    """评分引擎版本管理器"""
    
    # 类变量：版本存储
    _versions: Dict[str, ScoringEngineVersion] = {}
    _active_version_id: Optional[str] = None
    _version_history: List[Dict[str, Any]] = []
    
    @classmethod
    def register_version(
        cls,
        version_id: str,
        config: Dict[str, Any],
        description: str = "",
        author: str = ""
    ) -> tuple[bool, Optional[str]]:
        """
        注册新的评分引擎版本
        
        Args:
            version_id: 版本 ID (唯一标识)
            config: 评分算法配置
            description: 版本描述
            author: 作者信息
        
        Returns:
            (success, error_message)
        """
        # 检查版本是否已存在
        if version_id in cls._versions:
            return False, f"版本 {version_id} 已存在"
        
        # 创建版本对象
        metadata = {
            "description": description,
            "author": author
        }
        version = ScoringEngineVersion(version_id, config, metadata)
        
        # 验证版本
        is_valid, error_msg = version.validate()
        if not is_valid:
            return False, error_msg
        
        # 保存版本
        cls._versions[version_id] = version
        
        # 记录历史
        cls._record_history("register", version_id, {"config": config})
        
        return True, None
    
    @classmethod
    def switch_version(cls, version_id: str) -> tuple[bool, Optional[str]]:
        """
        切换到指定的版本
        
        Args:
            version_id: 要激活的版本 ID
        
        Returns:
            (success, error_message)
        """
        if version_id not in cls._versions:
            return False, f"版本 {version_id} 不存在"
        
        old_version = cls._active_version_id
        cls._active_version_id = version_id
        
        # 记录历史
        cls._record_history("switch", version_id, {
            "from_version": old_version,
            "to_version": version_id
        })
        
        return True, None
    
    @classmethod
    def get_active_version(cls) -> Optional[ScoringEngineVersion]:
        """获取当前激活的版本"""
        if cls._active_version_id is None:
            return None
        return cls._versions.get(cls._active_version_id)
    
    @classmethod
    def get_active_version_id(cls) -> Optional[str]:
        """获取当前激活的版本 ID"""
        return cls._active_version_id
    
    @classmethod
    def get_version(cls, version_id: str) -> Optional[ScoringEngineVersion]:
        """获取指定版本"""
        return cls._versions.get(version_id)
    
    @classmethod
    def list_versions(cls) -> List[Dict[str, Any]]:
        """列出所有版本"""
        result = []
        for version_id, version in cls._versions.items():
            result.append({
                "version_id": version_id,
                "is_active": version_id == cls._active_version_id,
                "config": version.algorithm_config,
                "metadata": version.metadata
            })
        return result
    
    @classmethod
    def get_version_config(cls, version_id: str) -> Optional[Dict[str, Any]]:
        """获取指定版本的配置"""
        version = cls.get_version(version_id)
        if version:
            return version.algorithm_config
        return None
    
    @classmethod
    def delete_version(cls, version_id: str) -> tuple[bool, Optional[str]]:
        """
        删除版本（不能删除激活的版本）
        
        Args:
            version_id: 要删除的版本 ID
        
        Returns:
            (success, error_message)
        """
        if version_id == cls._active_version_id:
            return False, "不能删除激活的版本，请先切换到其他版本"
        
        if version_id not in cls._versions:
            return False, f"版本 {version_id} 不存在"
        
        del cls._versions[version_id]
        cls._record_history("delete", version_id, {})
        
        return True, None
    
    @classmethod
    def export_version(cls, version_id: str) -> Optional[Dict[str, Any]]:
        """导出版本为 JSON 格式"""
        version = cls.get_version(version_id)
        if version:
            return version.to_dict()
        return None
    
    @classmethod
    def export_all_versions(cls) -> Dict[str, Any]:
        """导出所有版本"""
        return {
            "active_version": cls._active_version_id,
            "versions": {
                vid: version.to_dict()
                for vid, version in cls._versions.items()
            }
        }
    
    @classmethod
    def import_version(cls, version_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """导入版本配置"""
        try:
            version = ScoringEngineVersion.from_dict(version_data)
            
            # 如果版本已存在，不导入
            if version.version_id in cls._versions:
                return False, f"版本 {version.version_id} 已存在"
            
            # 验证版本
            is_valid, error_msg = version.validate()
            if not is_valid:
                return False, error_msg
            
            # 保存版本
            cls._versions[version.version_id] = version
            cls._record_history("import", version.version_id, version_data)
            
            return True, None
        except Exception as e:
            return False, f"导入失败: {str(e)}"
    
    @classmethod
    def get_history(cls, limit: int = 20) -> List[Dict[str, Any]]:
        """获取版本管理历史"""
        return cls._version_history[-limit:]
    
    @classmethod
    def clear_logs(cls):
        """清空所有数据（用于测试）"""
        cls._versions.clear()
        cls._active_version_id = None
        cls._version_history.clear()
    
    @classmethod
    def _record_history(cls, action: str, version_id: str, details: Dict[str, Any]):
        """记录版本管理历史"""
        cls._version_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "version_id": version_id,
            "details": details
        })


# 预定义的默认版本配置

DEFAULT_VERSION_V1 = {
    "version_id": "v1.0",
    "config": {
        "hard_skills_weight": 0.4,
        "soft_skills_weight": 0.2,
        "experience_weight": 0.2,
        "education_weight": 0.1,
        "language_weight": 0.1
    },
    "description": "基础版本，均衡的多维度评分"
}

IMPROVED_VERSION_V2 = {
    "version_id": "v2.0",
    "config": {
        "hard_skills_weight": 0.5,
        "soft_skills_weight": 0.15,
        "experience_weight": 0.25,
        "education_weight": 0.05,
        "language_weight": 0.05
    },
    "description": "改进版本，突出硬技能和经验"
}

SKILL_FOCUS_VERSION = {
    "version_id": "v2_skill_focus",
    "config": {
        "hard_skills_weight": 0.6,
        "soft_skills_weight": 0.2,
        "experience_weight": 0.15,
        "education_weight": 0.02,
        "language_weight": 0.03
    },
    "description": "技能优先版本，适合技术职位"
}

EXPERIENCE_FOCUS_VERSION = {
    "version_id": "v2_experience_focus",
    "config": {
        "hard_skills_weight": 0.3,
        "soft_skills_weight": 0.2,
        "experience_weight": 0.4,
        "education_weight": 0.05,
        "language_weight": 0.05
    },
    "description": "经验优先版本，适合管理职位"
}


def initialize_default_versions():
    """初始化默认版本"""
    for version_def in [DEFAULT_VERSION_V1, IMPROVED_VERSION_V2, SKILL_FOCUS_VERSION, EXPERIENCE_FOCUS_VERSION]:
        VersionManager.register_version(
            version_id=version_def["version_id"],
            config=version_def["config"],
            description=version_def["description"]
        )
    
    # 激活默认版本
    VersionManager.switch_version("v1.0")
