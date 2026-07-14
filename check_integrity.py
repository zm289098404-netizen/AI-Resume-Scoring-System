import sys
sys.path.insert(0, r'd:\AI_BUILD\TalentScope_Offline_20260607\src')

print("=" * 60)
print("📋 Phase 2 集成完整性检查")
print("=" * 60)

# ✓ 检查 1: 导入 ExceptionTracker
try:
    from talentscope.core.stability_framework import ExceptionTracker
    print("✅ [1/6] ExceptionTracker 导入成功")
except Exception as e:
    print(f"❌ [1/6] 导入失败: {e}")
    sys.exit(1)

# ✓ 检查 2: 测试基本功能
try:
    result, exc_id = ExceptionTracker.handle_with_fallback(
        "integrity_check",
        lambda: {"status": "ok"},
        {},
        max_retries=1
    )
    assert result["status"] == "ok"
    assert exc_id is None
    print("✅ [2/6] handle_with_fallback 正常")
except Exception as e:
    print(f"❌ [2/6] 功能测试失败: {e}")
    sys.exit(1)

# ✓ 检查 3: 测试异常处理
try:
    result, exc_id = ExceptionTracker.handle_with_fallback(
        "test_fallback",
        lambda: 1/0,
        {"fallback": True},
        max_retries=1
    )
    assert result["fallback"] is True
    assert result["_is_fallback"] is True
    assert exc_id is not None
    print("✅ [3/6] 异常降级正常")
except Exception as e:
    print(f"❌ [3/6] 异常处理失败: {e}")
    sys.exit(1)

# ✓ 检查 4: 测试日志查询
try:
    logs = ExceptionTracker.get_logs()
    assert len(logs) >= 1
    print(f"✅ [4/6] 日志查询正常 (共 {len(logs)} 条记录)")
except Exception as e:
    print(f"❌ [4/6] 日志查询失败: {e}")
    sys.exit(1)

# ✓ 检查 5: 导入 pipeline
try:
    from talentscope.pipeline import run, run_from_library
    print("✅ [5/6] pipeline.py 导入成功")
except Exception as e:
    print(f"❌ [5/6] pipeline 导入失败: {e}")
    sys.exit(1)

# ✓ 检查 6: 验证降级函数
try:
    from talentscope.pipeline import _build_fallback_resume, _build_fallback_match
    resume = _build_fallback_resume("test.pdf", "测试", "e1e2e3e4")
    assert resume["_is_fallback"] is True
    assert resume["_exc_id"] == "e1e2e3e4"
    
    match = _build_fallback_match("test.pdf", "测试", "e1e2e3e4")
    assert match["_is_fallback"] is True
    assert match["_exc_id"] == "e1e2e3e4"
    print("✅ [6/6] 降级函数正常")
except Exception as e:
    print(f"❌ [6/6] 降级函数检查失败: {e}")
    sys.exit(1)

print("=" * 60)
print("✨ 所有检查通过！Phase 2 已完全集成")
print("=" * 60)
