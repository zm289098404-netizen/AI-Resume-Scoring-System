"""
Phase 3 版本管理和 A/B 测试框架单元测试
==========================================

测试覆盖：
- 版本管理系统 (VersionManager)
- A/B 测试框架 (ABTestRunner)
- 版本验证
- 测试分配和分析

运行命令：
    pytest tests/test_stability_phase3.py -v
"""

import pytest
import json
from talentscope.core.version_manager import (
    ScoringEngineVersion,
    VersionManager,
    DEFAULT_VERSION_V1,
    IMPROVED_VERSION_V2,
    initialize_default_versions
)
from talentscope.core.ab_test_engine import (
    ABTestConfig,
    ABTestRunner,
    ABTestResult,
    ABTestAnalysis
)


# ============================================================================
# 测试 1: 版本定义和验证
# ============================================================================

class TestScoringEngineVersion:
    """版本定义和验证测试"""
    
    def test_version_creation(self):
        """创建版本"""
        version = ScoringEngineVersion(
            version_id="v1.0",
            algorithm_config={"weight_a": 0.5, "weight_b": 0.5}
        )
        
        assert version.version_id == "v1.0"
        assert version.algorithm_config["weight_a"] == 0.5
        assert "created_at" in version.metadata
    
    def test_version_validation_valid(self):
        """有效版本验证"""
        version = ScoringEngineVersion(
            version_id="v2.0",
            algorithm_config={"skill_weight": 0.4, "exp_weight": 0.6}
        )
        
        is_valid, error = version.validate()
        assert is_valid is True
        assert error is None
    
    def test_version_validation_invalid_weights(self):
        """权重验证"""
        version = ScoringEngineVersion(
            version_id="v1",
            algorithm_config={"weight": 1.5}  # 超出范围
        )
        
        is_valid, error = version.validate()
        assert is_valid is False
        assert "必须在 0-1 之间" in error
    
    def test_version_to_from_dict(self):
        """版本序列化和反序列化"""
        original = ScoringEngineVersion(
            version_id="v1",
            algorithm_config={"w1": 0.3, "w2": 0.7}
        )
        
        data = original.to_dict()
        restored = ScoringEngineVersion.from_dict(data)
        
        assert restored.version_id == original.version_id
        assert restored.algorithm_config == original.algorithm_config


# ============================================================================
# 测试 2: 版本管理器
# ============================================================================

class TestVersionManager:
    """版本管理器测试"""
    
    def setup_method(self):
        """每个测试前清空数据"""
        VersionManager.clear_logs()
    
    def test_register_version(self):
        """注册版本"""
        success, error = VersionManager.register_version(
            version_id="v1.0",
            config={"skill_weight": 0.4, "exp_weight": 0.6},
            description="test version"
        )
        
        assert success is True
        assert error is None
    
    def test_register_duplicate_version(self):
        """注册重复的版本"""
        VersionManager.register_version("v1", {"w": 0.5})
        success, error = VersionManager.register_version("v1", {"w": 0.6})
        
        assert success is False
        assert "已存在" in error
    
    def test_switch_version(self):
        """切换版本"""
        VersionManager.register_version("v1", {"w": 0.5})
        VersionManager.register_version("v2", {"w": 0.6})
        
        VersionManager.switch_version("v1")
        active = VersionManager.get_active_version_id()
        assert active == "v1"
        
        VersionManager.switch_version("v2")
        active = VersionManager.get_active_version_id()
        assert active == "v2"
    
    def test_get_active_version(self):
        """获取激活的版本"""
        VersionManager.register_version("v1", {"w": 0.5})
        VersionManager.switch_version("v1")
        
        version = VersionManager.get_active_version()
        assert version is not None
        assert version.version_id == "v1"
    
    def test_list_versions(self):
        """列出所有版本"""
        VersionManager.register_version("v1", {"w": 0.5})
        VersionManager.register_version("v2", {"w": 0.6})
        VersionManager.switch_version("v1")
        
        versions = VersionManager.list_versions()
        assert len(versions) == 2
        
        # 检查激活标记
        active_versions = [v for v in versions if v["is_active"]]
        assert len(active_versions) == 1
        assert active_versions[0]["version_id"] == "v1"
    
    def test_delete_version(self):
        """删除版本"""
        VersionManager.register_version("v1", {"w": 0.5})
        VersionManager.register_version("v2", {"w": 0.6})
        
        success, error = VersionManager.delete_version("v1")
        assert success is True
        
        versions = VersionManager.list_versions()
        assert len(versions) == 1
    
    def test_cannot_delete_active_version(self):
        """不能删除激活的版本"""
        VersionManager.register_version("v1", {"w": 0.5})
        VersionManager.switch_version("v1")
        
        success, error = VersionManager.delete_version("v1")
        assert success is False
        assert "激活" in error
    
    def test_get_version_config(self):
        """获取版本配置"""
        config = {"skill_weight": 0.5, "exp_weight": 0.5}
        VersionManager.register_version("v1", config)
        
        retrieved_config = VersionManager.get_version_config("v1")
        assert retrieved_config == config
    
    def test_export_import_version(self):
        """导出和导入版本"""
        config = {"w1": 0.3, "w2": 0.7}
        VersionManager.register_version("v1", config, description="test")
        
        # 导出
        exported = VersionManager.export_version("v1")
        assert exported["version_id"] == "v1"
        
        # 导入到新版本
        VersionManager.clear_logs()
        success, error = VersionManager.import_version(exported)
        assert success is True
        
        # 验证导入成功
        versions = VersionManager.list_versions()
        assert len(versions) == 1
    
    def test_export_all_versions(self):
        """导出所有版本"""
        VersionManager.register_version("v1", {"w": 0.5})
        VersionManager.register_version("v2", {"w": 0.6})
        VersionManager.switch_version("v1")
        
        exported = VersionManager.export_all_versions()
        assert exported["active_version"] == "v1"
        assert len(exported["versions"]) == 2
    
    def test_version_history(self):
        """版本管理历史"""
        VersionManager.register_version("v1", {"w": 0.5})
        VersionManager.register_version("v2", {"w": 0.6})
        VersionManager.switch_version("v1")
        
        history = VersionManager.get_history()
        assert len(history) >= 3
        
        # 检查历史类型
        actions = [h["action"] for h in history]
        assert "register" in actions
        assert "switch" in actions


# ============================================================================
# 测试 3: A/B 测试配置
# ============================================================================

class TestABTestConfig:
    """A/B 测试配置验证"""
    
    def test_config_validation_valid(self):
        """有效配置"""
        config = ABTestConfig(
            test_id="test_001",
            version_a="v1",
            version_b="v2",
            split_ratio=0.5
        )
        
        is_valid, error = config.validate()
        assert is_valid is True
        assert error is None
    
    def test_config_validation_same_versions(self):
        """版本相同"""
        config = ABTestConfig(
            test_id="test",
            version_a="v1",
            version_b="v1"
        )
        
        is_valid, error = config.validate()
        assert is_valid is False
        assert "不能相同" in error
    
    def test_config_validation_invalid_ratio(self):
        """无效的分配比例"""
        config = ABTestConfig(
            test_id="test",
            version_a="v1",
            version_b="v2",
            split_ratio=1.5
        )
        
        is_valid, error = config.validate()
        assert is_valid is False


# ============================================================================
# 测试 4: A/B 测试执行
# ============================================================================

class TestABTestRunner:
    """A/B 测试执行器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.runner = ABTestRunner()
    
    def test_register_test(self):
        """注册测试"""
        config = ABTestConfig("test_001", "v1", "v2", 0.5)
        success, error = self.runner.register_test(config)
        
        assert success is True
        assert error is None
    
    def test_assign_candidates(self):
        """分配候选人"""
        config = ABTestConfig("test_001", "v1", "v2", 0.5)
        
        candidates = [
            {"id": f"c{i}", "name": f"candidate{i}"}
            for i in range(100)
        ]
        
        groups = self.runner.assign_candidates(candidates, config)
        
        assert "v1" in groups
        assert "v2" in groups
        assert len(groups["v1"]) + len(groups["v2"]) == 100
        
        # 分配比例大约是 50:50
        ratio_a = len(groups["v1"]) / 100
        assert 0.3 < ratio_a < 0.7  # 允许 30-70 的偏差
    
    def test_collect_result(self):
        """收集单个结果"""
        config = ABTestConfig("test_001", "v1", "v2")
        self.runner.register_test(config)
        
        success, error = self.runner.collect_result(
            "test_001", "v1", "c001", 85.5
        )
        
        assert success is True
    
    def test_collect_batch_results(self):
        """批量收集结果"""
        config = ABTestConfig("test_001", "v1", "v2")
        self.runner.register_test(config)
        
        results = [
            {"version": "v1", "candidate_id": "c001", "score": 85},
            {"version": "v2", "candidate_id": "c002", "score": 90},
        ]
        
        success, error = self.runner.collect_batch_results("test_001", results)
        assert success is True
    
    def test_analyze_results(self):
        """分析测试结果"""
        config = ABTestConfig("test_001", "v1", "v2")
        self.runner.register_test(config)
        
        # 添加测试数据
        for i in range(20):
            self.runner.collect_result("test_001", "v1", f"v1_c{i}", 70 + i % 10)
            self.runner.collect_result("test_001", "v2", f"v2_c{i}", 75 + i % 10)
        
        analysis = self.runner.analyze_results("test_001")
        
        assert analysis is not None
        assert analysis.version_a_count == 20
        assert analysis.version_b_count == 20
        assert analysis.version_a_mean > 0
        assert analysis.version_b_mean > 0
    
    def test_get_test_info(self):
        """获取测试信息"""
        config = ABTestConfig("test_001", "v1", "v2", 0.5, "test desc")
        self.runner.register_test(config)
        
        info = self.runner.get_test_info("test_001")
        
        assert info["test_id"] == "test_001"
        assert info["version_a"] == "v1"
        assert info["description"] == "test desc"
    
    def test_list_tests(self):
        """列出所有测试"""
        self.runner.register_test(ABTestConfig("test_001", "v1", "v2"))
        self.runner.register_test(ABTestConfig("test_002", "v2", "v3"))
        
        tests = self.runner.list_tests()
        assert len(tests) == 2
    
    def test_export_test_report(self):
        """导出测试报告"""
        config = ABTestConfig("test_001", "v1", "v2")
        self.runner.register_test(config)
        
        # 添加结果
        self.runner.collect_result("test_001", "v1", "c001", 85)
        self.runner.collect_result("test_001", "v2", "c002", 90)
        
        report = self.runner.export_test_report("test_001")
        
        assert report is not None
        assert "config" in report
        assert "analysis" in report
        assert "results" in report


# ============================================================================
# 测试 5: 集成场景
# ============================================================================

class TestPhase3Integration:
    """Phase 3 集成测试"""
    
    def test_version_manager_with_defaults(self):
        """使用默认版本"""
        # 清空之前的状态（因为 VersionManager 是全局单例）
        VersionManager.clear_logs()
        
        initialize_default_versions()
        
        versions = VersionManager.list_versions()
        assert len(versions) == 4
        
        active = VersionManager.get_active_version()
        assert active.version_id == "v1.0"
    
    def test_full_ab_test_workflow(self):
        """完整的 A/B 测试工作流"""
        # 1. 初始化版本
        VersionManager.register_version("v1", {"w": 0.5})
        VersionManager.register_version("v2", {"w": 0.6})
        
        # 2. 创建 A/B 测试
        config = ABTestConfig(
            test_id="ab_001",
            version_a="v1",
            version_b="v2",
            split_ratio=0.5,
            description="compare v1 vs v2"
        )
        
        runner = ABTestRunner()
        runner.register_test(config)
        
        # 3. 分配候选人
        candidates = [{"id": f"c{i}"} for i in range(50)]
        groups = runner.assign_candidates(candidates, config)
        
        # 4. 评分 (模拟)
        import random
        for version, group in groups.items():
            for candidate in group:
                score = random.uniform(60, 100)
                runner.collect_result("ab_001", version, candidate["id"], score)
        
        # 5. 分析
        analysis = runner.analyze_results("ab_001")
        
        assert analysis is not None
        assert analysis.version_a_count > 0
        assert analysis.version_b_count > 0
        
        # 6. 导出报告
        report = runner.export_test_report("ab_001")
        assert report is not None


# ============================================================================
# 测试执行
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
