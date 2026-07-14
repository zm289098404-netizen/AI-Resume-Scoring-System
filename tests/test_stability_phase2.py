"""
Phase 2 异常处理系统单元测试
============================

测试内容：
1. ExceptionTracker 基本功能
2. 异常重试机制
3. 降级处理
4. 异常日志记录和查询
5. 管道集成测试

运行命令：
    pytest tests/test_stability_phase2.py -v
"""

import pytest
import json
import time
from talentscope.core.stability_framework import ExceptionTracker


# ============================================================================
# 测试 1: 异常日志记录
# ============================================================================

class TestExceptionLogging:
    """异常日志记录测试"""
    
    def setup_method(self):
        """每个测试前清空日志"""
        ExceptionTracker.clear_logs()
    
    def test_log_exception_basic(self):
        """记录异常应该生成日志条目"""
        try:
            raise ValueError("测试异常")
        except ValueError as e:
            exc_id = ExceptionTracker.log_exception(
                e,
                operation="test_operation"
            )
        
        assert exc_id is not None
        logs = ExceptionTracker.get_logs()
        assert len(logs) == 1
        assert logs[0]["exc_id"] == exc_id
        assert logs[0]["exception_type"] == "ValueError"
        assert "测试异常" in logs[0]["exception_msg"]
    
    def test_log_exception_with_context(self):
        """记录异常时带上下文信息"""
        try:
            raise RuntimeError("处理失败")
        except RuntimeError as e:
            exc_id = ExceptionTracker.log_exception(
                e,
                operation="resume_parsing",
                context={"filename": "test.pdf"}
            )
        
        logs = ExceptionTracker.get_logs()
        assert logs[0]["context"]["filename"] == "test.pdf"
        assert logs[0]["operation"] == "resume_parsing"
    
    def test_custom_exc_id(self):
        """使用自定义异常ID"""
        try:
            raise Exception("error")
        except Exception as e:
            exc_id = ExceptionTracker.log_exception(
                e,
                operation="test",
                exc_id="CUSTOM123"
            )
        
        assert exc_id == "CUSTOM123"
        logs = ExceptionTracker.get_logs()
        assert logs[0]["exc_id"] == "CUSTOM123"


# ============================================================================
# 测试 2: 重试机制
# ============================================================================

class TestRetryMechanism:
    """重试机制测试"""
    
    def setup_method(self):
        ExceptionTracker.clear_logs()
    
    def test_success_on_first_attempt(self):
        """第一次尝试成功，无需重试"""
        def always_success():
            return {"result": "success"}
        
        result, exc_id = ExceptionTracker.handle_with_fallback(
            "test_success",
            always_success,
            {"fallback": True},
            max_retries=3
        )
        
        assert result["result"] == "success"
        assert exc_id is None
        assert len(ExceptionTracker.get_logs()) == 0
    
    def test_retry_then_success(self):
        """重试后成功"""
        call_count = [0]
        
        def fail_then_succeed():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("暂时失败")
            return {"result": "success_after_retry"}
        
        result, exc_id = ExceptionTracker.handle_with_fallback(
            "test_retry",
            fail_then_succeed,
            {"fallback": True},
            max_retries=3
        )
        
        assert result["result"] == "success_after_retry"
        assert exc_id is not None  # 有异常但最终成功
        assert call_count[0] == 3
    
    def test_all_retries_fail_fallback(self):
        """所有重试都失败，返回降级值"""
        def always_fail():
            raise RuntimeError("永远失败")
        
        fallback = {"score": 0, "status": "fallback"}
        result, exc_id = ExceptionTracker.handle_with_fallback(
            "test_fallback",
            always_fail,
            fallback,
            max_retries=2
        )
        
        assert result["status"] == "fallback"
        assert result["_is_fallback"] is True
        assert exc_id is not None
        assert result["_exc_id"] == exc_id
    
    def test_exponential_backoff(self):
        """指数退避延迟"""
        start_time = time.time()
        
        def always_fail():
            raise Exception("fail")
        
        result, exc_id = ExceptionTracker.handle_with_fallback(
            "test_backoff",
            always_fail,
            {},
            max_retries=3
        )
        
        elapsed = time.time() - start_time
        # 预期延迟: 0s + 0.5s + 1s = 1.5s (±0.5s 误差范围)
        assert 1.0 < elapsed < 2.5


# ============================================================================
# 测试 3: 日志查询
# ============================================================================

class TestLogQuerying:
    """日志查询测试"""
    
    def setup_method(self):
        ExceptionTracker.clear_logs()
    
    def test_filter_by_operation(self):
        """按操作名称过滤日志"""
        # 创建多个不同操作的异常
        try:
            raise ValueError("error1")
        except ValueError as e:
            ExceptionTracker.log_exception(e, operation="parsing")
        
        try:
            raise ValueError("error2")
        except ValueError as e:
            ExceptionTracker.log_exception(e, operation="parsing")
        
        try:
            raise ValueError("error3")
        except ValueError as e:
            ExceptionTracker.log_exception(e, operation="scoring")
        
        # 查询特定操作
        parsing_logs = ExceptionTracker.get_logs(operation_filter="parsing")
        assert len(parsing_logs) == 2
        
        scoring_logs = ExceptionTracker.get_logs(operation_filter="scoring")
        assert len(scoring_logs) == 1
    
    def test_filter_by_exc_id(self):
        """按异常ID过滤日志"""
        exc_id_1 = ExceptionTracker.log_exception(
            Exception("error1"),
            operation="test"
        )
        
        exc_id_2 = ExceptionTracker.log_exception(
            Exception("error2"),
            operation="test"
        )
        
        logs_1 = ExceptionTracker.get_logs(exc_id_filter=exc_id_1)
        assert len(logs_1) == 1
        assert logs_1[0]["exc_id"] == exc_id_1
    
    def test_limit_logs(self):
        """限制返回的日志数"""
        for i in range(10):
            try:
                raise Exception(f"error{i}")
            except Exception as e:
                ExceptionTracker.log_exception(e, operation="test")
        
        all_logs = ExceptionTracker.get_logs()
        assert len(all_logs) == 10
        
        limited_logs = ExceptionTracker.get_logs(limit=3)
        assert len(limited_logs) == 3


# ============================================================================
# 测试 4: 降级处理
# ============================================================================

class TestFallbackHandling:
    """降级处理测试"""
    
    def setup_method(self):
        ExceptionTracker.clear_logs()
    
    def test_fallback_preserves_structure(self):
        """降级值保持原有结构"""
        fallback = {
            "score": 0,
            "recommendation": "降级",
            "risks": []
        }
        
        def failing_func():
            raise Exception("fail")
        
        result, exc_id = ExceptionTracker.handle_with_fallback(
            "test",
            failing_func,
            fallback,
            max_retries=1
        )
        
        assert result["score"] == 0
        assert result["recommendation"] == "降级"
        assert result["_is_fallback"] is True
    
    def test_fallback_with_context(self):
        """降级时保留上下文信息"""
        def failing_func():
            raise Exception("fail")
        
        result, exc_id = ExceptionTracker.handle_with_fallback(
            "resume_parsing",
            failing_func,
            {"status": "unknown"},
            max_retries=1,
            context={"filename": "resume.pdf"}
        )
        
        logs = ExceptionTracker.get_logs()
        assert logs[0]["context"]["filename"] == "resume.pdf"


# ============================================================================
# 测试 5: 日志导出
# ============================================================================

class TestLogExport:
    """日志导出测试"""
    
    def setup_method(self):
        ExceptionTracker.clear_logs()
    
    def test_export_logs_jsonl(self, tmp_path):
        """导出异常日志到JSONL文件"""
        # 创建一些异常日志
        for i in range(3):
            try:
                raise ValueError(f"error{i}")
            except ValueError as e:
                ExceptionTracker.log_exception(e, operation="test")
        
        # 导出
        export_path = tmp_path / "logs.jsonl"
        ExceptionTracker.export_logs_jsonl(str(export_path))
        
        # 验证
        with open(export_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        assert len(lines) == 3
        
        # 验证每一行都是有效的JSON
        for line in lines:
            log_entry = json.loads(line)
            assert "exc_id" in log_entry
            assert "exception_type" in log_entry


# ============================================================================
# 测试 6: 与管道集成模拟
# ============================================================================

class TestPipelineIntegration:
    """与管道集成的测试"""
    
    def setup_method(self):
        ExceptionTracker.clear_logs()
    
    def test_multiple_resume_processing(self):
        """处理多个简历时，一个失败不影响其他"""
        def mock_parse_resume(text):
            if "BAD" in text:
                raise ValueError("解析失败")
            return {"name": "candidate", "skills": []}
        
        results = []
        for filename in ["good1.pdf", "bad.pdf", "good2.pdf"]:
            text = filename.replace(".pdf", "").upper()
            result, exc_id = ExceptionTracker.handle_with_fallback(
                "resume_parsing",
                mock_parse_resume,
                {"name": "—", "skills": []},
                text,
                max_retries=1,
                context={"filename": filename}
            )
            results.append((filename, result, exc_id))
        
        # 验证：所有文件都有结果，即使有失败
        assert len(results) == 3
        
        # 检查：中间的那个应该有异常ID
        assert results[0][2] is None  # good1: 成功
        assert results[1][2] is not None  # bad: 失败，有exc_id
        assert results[2][2] is None  # good2: 成功
        
        # 检查日志：应该只有1个异常
        logs = ExceptionTracker.get_logs()
        assert len(logs) == 1
    
    def test_exc_id_tracking(self):
        """异常ID跟踪"""
        results_with_exc = []
        
        for i in range(3):
            def func_that_sometimes_fails():
                if i == 1:
                    raise RuntimeError(f"attempt {i}")
                return {"data": f"result{i}"}
            
            result, exc_id = ExceptionTracker.handle_with_fallback(
                "operation",
                func_that_sometimes_fails,
                {},
                max_retries=2,
                context={"attempt": i}
            )
            
            if exc_id:
                results_with_exc.append(exc_id)
        
        # 应该只有一个失败
        assert len(results_with_exc) == 1


# ============================================================================
# 测试执行
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
