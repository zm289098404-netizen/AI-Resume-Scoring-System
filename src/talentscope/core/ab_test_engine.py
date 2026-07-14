"""
Phase 3: A/B 测试引擎
=======================

提供 A/B 测试功能，支持：
- A/B 测试配置定义
- 按配置比例随机分配候选人
- 结果收集和分析
- 统计显著性检验
- 结果导出

使用示例：
    from talentscope.core.ab_test_engine import ABTestRunner, ABTestConfig
    
    # 创建测试配置
    config = ABTestConfig(
        test_id="test_001",
        version_a="v1.0",
        version_b="v2.0",
        split_ratio=0.5,
        description="compare v1 vs v2"
    )
    
    # 执行测试
    runner = ABTestRunner()
    ab_groups = runner.assign_candidates([...], config)
    # ab_groups = {"v1.0": [...], "v2.0": [...]}
    
    # 收集结果
    runner.collect_result("test_001", "v1.0", candidate_id, score)
    
    # 分析结果
    analysis = runner.analyze_results("test_001")
"""

import random
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class ABTestConfig:
    """A/B 测试配置"""
    test_id: str  # 唯一测试ID
    version_a: str  # 版本A的ID
    version_b: str  # 版本B的ID
    split_ratio: float = 0.5  # 流量分配比例 (0-1)
    description: str = ""  # 测试描述
    created_at: Optional[str] = None  # 创建时间
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """验证配置有效性"""
        if not isinstance(self.test_id, str) or not self.test_id.strip():
            return False, "test_id 不能为空"
        
        if not isinstance(self.version_a, str) or not self.version_a.strip():
            return False, "version_a 不能为空"
        
        if not isinstance(self.version_b, str) or not self.version_b.strip():
            return False, "version_b 不能为空"
        
        if self.version_a == self.version_b:
            return False, "version_a 和 version_b 不能相同"
        
        if not (0 < self.split_ratio < 1):
            return False, "split_ratio 必须在 0-1 之间（不包括 0 和 1）"
        
        return True, None


class ABTestResult:
    """单个 A/B 测试结果"""
    
    def __init__(self, test_id: str, version: str, candidate_id: str, score: float):
        """
        Args:
            test_id: 测试ID
            version: 使用的版本
            candidate_id: 候选人ID
            score: 评分结果
        """
        self.test_id = test_id
        self.version = version
        self.candidate_id = candidate_id
        self.score = score
        self.recorded_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "version": self.version,
            "candidate_id": self.candidate_id,
            "score": self.score,
            "recorded_at": self.recorded_at
        }


class ABTestAnalysis:
    """A/B 测试分析结果"""
    
    def __init__(self, test_id: str, version_a: str, version_b: str):
        self.test_id = test_id
        self.version_a = version_a
        self.version_b = version_b
        self.analysis_time = datetime.now().isoformat()
        
        # 统计数据 (需要在分析时填充)
        self.version_a_results: List[float] = []
        self.version_b_results: List[float] = []
        self.version_a_count = 0
        self.version_b_count = 0
        self.version_a_mean = 0.0
        self.version_b_mean = 0.0
        self.version_a_std = 0.0
        self.version_b_std = 0.0
        self.improvement_percent = 0.0
        self.is_significant = False
    
    def compute_statistics(self):
        """计算统计数据"""
        if not self.version_a_results or not self.version_b_results:
            return
        
        # 计数
        self.version_a_count = len(self.version_a_results)
        self.version_b_count = len(self.version_b_results)
        
        # 平均值
        self.version_a_mean = sum(self.version_a_results) / self.version_a_count
        self.version_b_mean = sum(self.version_b_results) / self.version_b_count
        
        # 标准差
        if self.version_a_count > 1:
            variance_a = sum((x - self.version_a_mean) ** 2 for x in self.version_a_results) / (self.version_a_count - 1)
            self.version_a_std = variance_a ** 0.5
        
        if self.version_b_count > 1:
            variance_b = sum((x - self.version_b_mean) ** 2 for x in self.version_b_results) / (self.version_b_count - 1)
            self.version_b_std = variance_b ** 0.5
        
        # 改进百分比
        if self.version_a_mean != 0:
            self.improvement_percent = (self.version_b_mean - self.version_a_mean) / self.version_a_mean * 100
        
        # 简单的显著性判断 (Cohen's d)
        # d = (mean_b - mean_a) / pooled_std
        if self.version_a_std > 0 or self.version_b_std > 0:
            pooled_std = (
                (self.version_a_count - 1) * (self.version_a_std ** 2) +
                (self.version_b_count - 1) * (self.version_b_std ** 2)
            ) / (self.version_a_count + self.version_b_count - 2)
            pooled_std = pooled_std ** 0.5
            
            if pooled_std > 0:
                cohens_d = (self.version_b_mean - self.version_a_mean) / pooled_std
                # 如果 Cohen's d > 0.2，认为有显著差异
                self.is_significant = abs(cohens_d) > 0.2
    
    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "version_a": self.version_a,
            "version_b": self.version_b,
            "analysis_time": self.analysis_time,
            "version_a_count": self.version_a_count,
            "version_b_count": self.version_b_count,
            "version_a_mean": round(self.version_a_mean, 4),
            "version_b_mean": round(self.version_b_mean, 4),
            "version_a_std": round(self.version_a_std, 4),
            "version_b_std": round(self.version_b_std, 4),
            "improvement_percent": round(self.improvement_percent, 2),
            "is_significant": self.is_significant
        }


class ABTestRunner:
    """A/B 测试执行器"""
    
    def __init__(self):
        self._tests: Dict[str, ABTestConfig] = {}
        self._results: Dict[str, List[ABTestResult]] = {}
        self._assignments: Dict[str, Dict[str, str]] = {}  # test_id -> {candidate_id: version}
    
    def register_test(self, config: ABTestConfig) -> Tuple[bool, Optional[str]]:
        """注册新的 A/B 测试"""
        # 验证配置
        is_valid, error_msg = config.validate()
        if not is_valid:
            return False, error_msg
        
        # 检查是否已存在
        if config.test_id in self._tests:
            return False, f"测试 {config.test_id} 已存在"
        
        self._tests[config.test_id] = config
        self._results[config.test_id] = []
        self._assignments[config.test_id] = {}
        
        return True, None
    
    def assign_candidates(
        self,
        candidates: List[Dict[str, Any]],
        config: ABTestConfig
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        按配置比例分配候选人到两个版本
        
        Args:
            candidates: 候选人列表
            config: A/B 测试配置
        
        Returns:
            {version_a: [...], version_b: [...]}
        """
        if config.test_id not in self._tests:
            # 自动注册配置
            self.register_test(config)
        
        # 重置分配
        self._assignments[config.test_id] = {}
        
        # 按比例分配
        group_a = []
        group_b = []
        
        for candidate in candidates:
            candidate_id = candidate.get("id", str(uuid.uuid4()))
            
            if random.random() < config.split_ratio:
                group_a.append(candidate)
                self._assignments[config.test_id][candidate_id] = config.version_a
            else:
                group_b.append(candidate)
                self._assignments[config.test_id][candidate_id] = config.version_b
        
        return {
            config.version_a: group_a,
            config.version_b: group_b
        }
    
    def collect_result(
        self,
        test_id: str,
        version: str,
        candidate_id: str,
        score: float
    ) -> Tuple[bool, Optional[str]]:
        """
        收集单个测试结果
        
        Args:
            test_id: 测试ID
            version: 使用的版本
            candidate_id: 候选人ID
            score: 评分结果
        
        Returns:
            (success, error_message)
        """
        if test_id not in self._tests:
            return False, f"测试 {test_id} 不存在"
        
        result = ABTestResult(test_id, version, candidate_id, score)
        self._results[test_id].append(result)
        
        return True, None
    
    def collect_batch_results(
        self,
        test_id: str,
        results: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[str]]:
        """
        批量收集测试结果
        
        Args:
            test_id: 测试ID
            results: 结果列表 [{"version": "v1", "candidate_id": "x", "score": 85}, ...]
        
        Returns:
            (success, error_message)
        """
        for result_data in results:
            version = result_data.get("version")
            candidate_id = result_data.get("candidate_id")
            score = result_data.get("score")
            
            success, error_msg = self.collect_result(test_id, version, candidate_id, score)
            if not success:
                return False, error_msg
        
        return True, None
    
    def analyze_results(self, test_id: str) -> Optional[ABTestAnalysis]:
        """
        分析测试结果
        
        Args:
            test_id: 测试ID
        
        Returns:
            分析结果对象或 None（如果测试不存在）
        """
        if test_id not in self._tests:
            return None
        
        config = self._tests[test_id]
        results = self._results[test_id]
        
        # 创建分析对象
        analysis = ABTestAnalysis(test_id, config.version_a, config.version_b)
        
        # 分离结果
        for result in results:
            if result.version == config.version_a:
                analysis.version_a_results.append(result.score)
            elif result.version == config.version_b:
                analysis.version_b_results.append(result.score)
        
        # 计算统计数据
        analysis.compute_statistics()
        
        return analysis
    
    def get_test_info(self, test_id: str) -> Optional[Dict[str, Any]]:
        """获取测试信息"""
        if test_id not in self._tests:
            return None
        
        config = self._tests[test_id]
        results = self._results[test_id]
        
        return {
            "test_id": config.test_id,
            "version_a": config.version_a,
            "version_b": config.version_b,
            "split_ratio": config.split_ratio,
            "description": config.description,
            "created_at": config.created_at,
            "results_count": len(results)
        }
    
    def get_results(
        self,
        test_id: str,
        version_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取测试结果"""
        if test_id not in self._results:
            return []
        
        results = self._results[test_id]
        
        if version_filter:
            results = [r for r in results if r.version == version_filter]
        
        return [r.to_dict() for r in results]
    
    def list_tests(self) -> List[Dict[str, Any]]:
        """列出所有注册的测试"""
        tests = []
        for test_id, config in self._tests.items():
            results_count = len(self._results.get(test_id, []))
            tests.append({
                "test_id": config.test_id,
                "version_a": config.version_a,
                "version_b": config.version_b,
                "split_ratio": config.split_ratio,
                "description": config.description,
                "created_at": config.created_at,
                "results_count": results_count
            })
        return tests
    
    def export_test_report(self, test_id: str) -> Optional[Dict[str, Any]]:
        """导出完整的测试报告"""
        config = self._tests.get(test_id)
        analysis = self.analyze_results(test_id)
        results = self.get_results(test_id)
        
        if not config or not analysis:
            return None
        
        return {
            "config": asdict(config),
            "analysis": analysis.to_dict(),
            "results": results
        }
    
    def clear_test(self, test_id: str) -> Tuple[bool, Optional[str]]:
        """清除测试数据"""
        if test_id not in self._tests:
            return False, f"测试 {test_id} 不存在"
        
        del self._tests[test_id]
        del self._results[test_id]
        del self._assignments[test_id]
        
        return True, None
    
    def clear_all_tests(self):
        """清除所有测试数据"""
        self._tests.clear()
        self._results.clear()
        self._assignments.clear()
