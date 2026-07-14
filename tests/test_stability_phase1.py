"""
Phase 1 稳定性框架单元测试
==========================

测试内容：
1. JSON Schema 验证
2. 自动修复
3. 安全 JSON 解析
4. 降级处理
5. 置信度计算

运行命令：
    pytest tests/test_stability_phase1.py -v
"""

import pytest
import json
from talentscope.core.stability_framework import (
    MatchResultValidator,
    safe_json_loads,
)


# ============================================================================
# 测试 1: JSON Schema 验证
# ============================================================================

class TestMatchResultValidator:
    """匹配结果验证测试"""
    
    def test_valid_result_passes(self):
        """有效结果应该通过验证"""
        valid_result = {
            "total_score": 85.5,
            "dimensions": {
                "hard_skill": 88,
                "experience": 90,
                "soft_skill": 75,
                "education": 80
            },
            "matched_skills": ["Python", "SQL"],
            "missing_skills": ["Go"],
            "recommendation": "Excellent match for this senior position."
        }
        is_valid, error_msg, fixed = MatchResultValidator.validate(valid_result)
        assert is_valid, f"应该通过: {error_msg}"
        assert error_msg == ""
    
    def test_missing_required_fields(self):
        """缺少必需字段应该失败并自动修复"""
        invalid_result = {
            "total_score": 85.5,
            "dimensions": {"hard_skill": 88},
            "matched_skills": []
        }
        is_valid, error_msg, fixed = MatchResultValidator.validate(invalid_result)
        # 自动修复应该成功
        assert is_valid or "自动修复" in error_msg
        assert "recommendation" in fixed
    
    def test_null_recommendation_fixed(self):
        """null的recommendation应该自动修复"""
        invalid_result = {
            "total_score": 85.5,
            "dimensions": {
                "hard_skill": 88,
                "experience": 90,
                "soft_skill": 75,
                "education": 80
            },
            "matched_skills": [],
            "missing_skills": [],
            "recommendation": None
        }
        is_valid, error_msg, fixed = MatchResultValidator.validate(invalid_result)
        assert is_valid or "自动修复" in error_msg
        assert isinstance(fixed["recommendation"], str)
        assert len(fixed["recommendation"]) >= 10
    
    def test_out_of_range_score_fixed(self):
        """超出范围的分数应该被修复到0-100"""
        invalid_result = {
            "total_score": 150.0,  # 超过100
            "dimensions": {
                "hard_skill": 88,
                "experience": 90,
                "soft_skill": 75,
                "education": 80
            },
            "matched_skills": [],
            "missing_skills": [],
            "recommendation": "Test"
        }
        is_valid, error_msg, fixed = MatchResultValidator.validate(invalid_result)
        assert fixed["total_score"] <= 100.0
        assert fixed["total_score"] >= 0.0
    
    def test_string_score_converted(self):
        """字符串分数应该转换为数字"""
        invalid_result = {
            "total_score": "85.5",  # 字符串
            "dimensions": {
                "hard_skill": "88",
                "experience": 90,
                "soft_skill": 75,
                "education": 80
            },
            "matched_skills": [],
            "missing_skills": [],
            "recommendation": "Test"
        }
        is_valid, error_msg, fixed = MatchResultValidator.validate(invalid_result)
        assert is_valid or "自动修复" in error_msg
        assert isinstance(fixed["total_score"], (int, float))
        assert isinstance(fixed["dimensions"]["hard_skill"], (int, float))
    
    def test_missing_interview_questions_filled(self):
        """缺少interview_questions应该填充默认值"""
        invalid_result = {
            "total_score": 85.5,
            "dimensions": {
                "hard_skill": 88,
                "experience": 90,
                "soft_skill": 75,
                "education": 80
            },
            "matched_skills": [],
            "missing_skills": [],
            "recommendation": "Test"
        }
        is_valid, error_msg, fixed = MatchResultValidator.validate(invalid_result)
        assert is_valid or "自动修复" in error_msg
        assert "interview_questions" in fixed
        assert len(fixed["interview_questions"]) >= 1
        assert all(isinstance(q, str) for q in fixed["interview_questions"])
    
    def test_semantic_check_score_dimension_mismatch(self):
        """语义检查应该发现总分与维度严重不匹配"""
        result = {
            "total_score": 10.0,  # 非常低
            "dimensions": {
                "hard_skill": 90,
                "experience": 95,
                "soft_skill": 85,
                "education": 92
            },
            "matched_skills": [],
            "missing_skills": [],
            "recommendation": "Test"
        }
        issues = MatchResultValidator.semantic_check(result)
        # 应该发现不一致
        assert len(issues) > 0, "应该发现维度与总分不一致"


# ============================================================================
# 测试 2: 安全 JSON 解析
# ============================================================================

class TestSafeJsonLoads:
    """安全JSON解析测试"""
    
    def test_valid_json(self):
        """有效的JSON应该直接解析"""
        text = '{"key": "value", "score": 85}'
        result = safe_json_loads(text)
        assert result["key"] == "value"
        assert result["score"] == 85
    
    def test_json_with_markdown_block(self):
        """带markdown代码块的JSON应该提取"""
        text = """
Here's the result:

```json
{"total_score": 85, "recommendation": "Good"}
```

That's it.
        """
        result = safe_json_loads(text)
        assert result["total_score"] == 85
        assert result["recommendation"] == "Good"
    
    def test_json_with_prefix_text(self):
        """前面带文字的JSON应该提取"""
        text = """
The analysis shows:
{"total_score": 75, "skills": ["Python", "Java"]}
Some more text after.
        """
        result = safe_json_loads(text)
        assert result["total_score"] == 75
        assert "Python" in result["skills"]
    
    def test_empty_response(self):
        """空响应应该返回错误对象"""
        result = safe_json_loads("")
        assert "_error" in result
    
    def test_malformed_json_fallback(self):
        """无法解析的JSON应该返回错误对象"""
        text = "Not valid JSON at all {broken"
        result = safe_json_loads(text)
        assert "_error" in result
    
    def test_nested_json_extraction(self):
        """包含嵌套JSON的文本应该提取"""
        text = """
Analysis:
{"outer": {"inner": {"score": 88}}, "name": "test"}
        """
        result = safe_json_loads(text)
        assert result["outer"]["inner"]["score"] == 88


# ============================================================================
# 测试 3: 集成测试（模拟完整流程）
# ============================================================================

class TestIntegration:
    """集成测试"""
    
    def test_complete_flow_valid(self):
        """完整流程：有效结果"""
        # 模拟LLM返回
        llm_response = json.dumps({
            "total_score": 85.5,
            "dimensions": {
                "hard_skill": 88,
                "experience": 90,
                "soft_skill": 75,
                "education": 80
            },
            "matched_skills": ["Python", "SQL"],
            "missing_skills": ["Go"],
            "recommendation": "This candidate is a strong match."
        })
        
        # 解析
        result = safe_json_loads(llm_response)
        
        # 验证
        is_valid, error_msg, fixed = MatchResultValidator.validate(result)
        
        # 断言
        assert is_valid
        assert fixed["total_score"] == 85.5
        assert "Python" in fixed["matched_skills"]
    
    def test_complete_flow_partial_corruption(self):
        """完整流程：部分损坏的结果"""
        # 模拟LLM返回（缺少字段）
        llm_response = json.dumps({
            "total_score": 85,
            "matched_skills": ["Python"],
            # 缺少其他字段
        })
        
        # 解析
        result = safe_json_loads(llm_response)
        
        # 验证（应该自动修复）
        is_valid, error_msg, fixed = MatchResultValidator.validate(result)
        
        # 即使不完全有效，也应该有所有必需字段
        assert "recommendation" in fixed
        assert "missing_skills" in fixed
        assert "dimensions" in fixed
    
    def test_complete_flow_extraction_from_text(self):
        """完整流程：从文本中提取JSON"""
        # 模拟LLM以文本形式返回JSON
        text = """
Based on the analysis:

```json
{
  "total_score": 90,
  "dimensions": {"hard_skill": 92, "experience": 88, "soft_skill": 87, "education": 90},
  "matched_skills": ["Python", "Docker"],
  "missing_skills": [],
  "recommendation": "Highly recommended for senior role."
}
```

This candidate is excellent.
        """
        
        # 解析
        result = safe_json_loads(text, context="test_extraction")
        
        # 验证
        is_valid, error_msg, fixed = MatchResultValidator.validate(result)
        
        # 断言
        assert "_error" not in result
        assert result["total_score"] == 90
        assert "Docker" in result["matched_skills"]


# ============================================================================
# 测试 4: 边界条件
# ============================================================================

class TestEdgeCases:
    """边界条件测试"""
    
    def test_recommendation_too_long_truncated(self):
        """超长recommendation应该被截断"""
        long_text = "A" * 1000
        result = {
            "total_score": 80,
            "dimensions": {"hard_skill": 80, "experience": 80, "soft_skill": 80, "education": 80},
            "matched_skills": [],
            "missing_skills": [],
            "recommendation": long_text
        }
        is_valid, error_msg, fixed = MatchResultValidator.validate(result)
        assert len(fixed["recommendation"]) <= 500
    
    def test_recommendation_too_short_expanded(self):
        """过短recommendation应该被扩展"""
        short_text = "Yes"
        result = {
            "total_score": 80,
            "dimensions": {"hard_skill": 80, "experience": 80, "soft_skill": 80, "education": 80},
            "matched_skills": [],
            "missing_skills": [],
            "recommendation": short_text
        }
        is_valid, error_msg, fixed = MatchResultValidator.validate(result)
        assert len(fixed["recommendation"]) >= 10
    
    def test_zero_score_allowed(self):
        """0分应该被允许"""
        result = {
            "total_score": 0,
            "dimensions": {"hard_skill": 0, "experience": 0, "soft_skill": 0, "education": 0},
            "matched_skills": [],
            "missing_skills": ["all"],
            "recommendation": "Not a fit."
        }
        is_valid, error_msg, fixed = MatchResultValidator.validate(result)
        assert is_valid or "自动修复" in error_msg
        assert fixed["total_score"] == 0
    
    def test_hundred_score_allowed(self):
        """100分应该被允许"""
        result = {
            "total_score": 100,
            "dimensions": {"hard_skill": 100, "experience": 100, "soft_skill": 100, "education": 100},
            "matched_skills": ["all"],
            "missing_skills": [],
            "recommendation": "Perfect fit."
        }
        is_valid, error_msg, fixed = MatchResultValidator.validate(result)
        assert is_valid or "自动修复" in error_msg
        assert fixed["total_score"] == 100


# ============================================================================
# 测试执行
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
