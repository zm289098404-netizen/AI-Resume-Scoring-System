"""
TalentScope 稳定性框架 - Phase 1: 格式约束与验证
================================================

本模块实现 JSON Schema 验证、自动修复和安全的JSON解析。

Quick Start:
    from talentscope.core.stability_framework import (
        MatchResultValidator,
        safe_json_loads,
    )
    
    # 验证匹配结果
    is_valid, error_msg, fixed = MatchResultValidator.validate(result)
    
    # 安全解析JSON
    result = safe_json_loads(llm_response, context="matching")
"""

import json
import re
import logging
from typing import Tuple, Optional
import jsonschema

logger = logging.getLogger(__name__)


# ============================================================================
# Layer 1: 格式约束与验证
# ============================================================================

class MatchResultValidator:
    """匹配结果的JSON Schema验证"""
    
    SCHEMA = {
        "$schema": "http://json-schema.org/draft-7/schema#",
        "type": "object",
        "required": [
            "total_score",
            "dimensions",
            "matched_skills",
            "missing_skills",
            "recommendation"
        ],
        "properties": {
            "total_score": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "总体匹配分数，0-100"
            },
            "dimensions": {
                "type": "object",
                "required": ["hard_skill", "experience", "soft_skill", "education"],
                "properties": {
                    "hard_skill": {"type": "number", "minimum": 0, "maximum": 100},
                    "experience": {"type": "number", "minimum": 0, "maximum": 100},
                    "soft_skill": {"type": "number", "minimum": 0, "maximum": 100},
                    "education": {"type": "number", "minimum": 0, "maximum": 100}
                },
                "additionalProperties": False
            },
            "matched_skills": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 0
            },
            "missing_skills": {
                "type": "array",
                "items": {"type": "string"}
            },
            "recommendation": {
                "type": "string",
                "minLength": 10,
                "maxLength": 500
            },
            "risks": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 5
            },
            "interview_questions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 5
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
            },
            "_jd_hard_skills_count": {
                "type": "integer"
            }
        },
        "additionalProperties": True
    }
    
    @staticmethod
    def validate(result: dict) -> Tuple[bool, str, dict]:
        """
        验证匹配结果
        
        Args:
            result: 匹配结果字典
        
        Returns:
            (是否有效, 错误消息, 修复后的结果)
        """
        try:
            jsonschema.validate(result, MatchResultValidator.SCHEMA)
            return True, "", result
        except jsonschema.ValidationError as e:
            fixed = MatchResultValidator._auto_fix(result, e)
            try:
                jsonschema.validate(fixed, MatchResultValidator.SCHEMA)
                logger.info(f"自动修复成功: {e.message}")
                return True, f"自动修复: {e.message}", fixed
            except jsonschema.ValidationError as e2:
                logger.warning(f"验证失败: {e2.message}")
                return False, f"验证失败: {e2.message}", result
    
    @staticmethod
    def _auto_fix(result: dict, error: jsonschema.ValidationError) -> dict:
        """自动修复常见错误"""
        result = dict(result)  # 浅拷贝
        
        # 修复0：确保所有必需的顶层字段存在
        required_fields = {
            "total_score": 50.0,
            "dimensions": {
                "hard_skill": 50,
                "experience": 50,
                "soft_skill": 50,
                "education": 50
            },
            "matched_skills": [],
            "missing_skills": [],
            "recommendation": "候选人与岗位有一定的匹配度。"
        }
        
        for field, default in required_fields.items():
            if field not in result:
                result[field] = default
        
        # 修复1：缺少或无效的recommendation
        if "recommendation" not in result or not result.get("recommendation"):
            result["recommendation"] = "候选人与岗位需求有匹配度，建议进一步了解。"
        elif len(str(result["recommendation"])) < 10:
            result["recommendation"] += "（请在面试中深入考察相关能力。）"
        elif len(str(result["recommendation"])) > 500:
            result["recommendation"] = str(result["recommendation"])[:497] + "..."
        
        # 修复2：无效的risks
        if "risks" not in result or not isinstance(result.get("risks"), list):
            result["risks"] = []
        
        # 修复3：无效的interview_questions
        if "interview_questions" not in result or not result.get("interview_questions"):
            result["interview_questions"] = [
                "请详细介绍你在相关技术上的实际项目经验。",
                "如何在工作中应用这个领域的最佳实践？"
            ]
        
        # 修复4：score类型转换
        if "total_score" in result:
            val = result["total_score"]
            if isinstance(val, str):
                try:
                    result["total_score"] = float(val)
                except (ValueError, TypeError):
                    result["total_score"] = 50.0
            elif not isinstance(val, (int, float)):
                result["total_score"] = 50.0
            else:
                result["total_score"] = max(0.0, min(100.0, float(val)))
        
        # 修复5：dimensions有效性
        if "dimensions" in result and isinstance(result["dimensions"], dict):
            for key in ["hard_skill", "experience", "soft_skill", "education"]:
                if key not in result["dimensions"]:
                    result["dimensions"][key] = 50.0
                val = result["dimensions"].get(key)
                if not isinstance(val, (int, float)):
                    result["dimensions"][key] = 50.0
                else:
                    result["dimensions"][key] = max(0.0, min(100.0, float(val)))
        
        # 修复6：confidence
        if "confidence" in result:
            val = result["confidence"]
            if isinstance(val, (int, float)):
                result["confidence"] = max(0.0, min(1.0, float(val)))
            else:
                result["confidence"] = 0.5
        
        # 修复7：matched_skills 和 missing_skills 必须是列表
        if "matched_skills" not in result or not isinstance(result.get("matched_skills"), list):
            result["matched_skills"] = []
        if "missing_skills" not in result or not isinstance(result.get("missing_skills"), list):
            result["missing_skills"] = []
        
        return result
    
    @staticmethod
    def semantic_check(result: dict) -> list:
        """语义检查：逻辑合理性"""
        issues = []
        
        # 检查1：总分与维度一致性
        dims = result.get("dimensions", {})
        if isinstance(dims, dict) and dims:
            valid_dims = {v for v in dims.values() if isinstance(v, (int, float))}
            if valid_dims:
                avg_dim = sum(valid_dims) / len(valid_dims)
                total = result.get("total_score", 0)
                if abs(total - avg_dim) > 25:
                    issues.append(f"总分({total:.1f})与维度平均值({avg_dim:.1f})差异>25分")
        
        # 检查2：置信度异常低
        conf = result.get("confidence", 1.0)
        if conf < 0.2:
            issues.append(f"置信度过低({conf:.1%})，可能为严重降级")
        
        return issues


def safe_json_loads(text: str, context: str = "") -> dict:
    """
    安全的JSON解析，多层容错
    
    Args:
        text: 原始文本
        context: 用于日志的上下文信息
    
    Returns:
        解析后的dict（或错误对象）
    """
    text = text.strip() if text else ""
    
    if not text:
        return {"_error": "空响应", "_context": context}
    
    # 第一步：去除前导文本
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith("{"):
            text = "\n".join(lines[i:])
            break
    
    # 第二步：去除markdown代码块
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            if part.strip().startswith("{"):
                cleaned = re.sub(r"^json\s*", "", part.strip())
                if cleaned.startswith("{"):
                    text = cleaned
                    break
    
    # 第三步：标准JSON解析
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.debug(f"标准JSON解析失败 [{context}]: {e}")
    
    # 第四步：提取所有{...}对（贪心）
    json_matches = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    
    for match in json_matches:
        try:
            parsed = json.loads(match)
            logger.info(f"JSON提取成功 [{context}]")
            return parsed
        except json.JSONDecodeError:
            continue
    
    # 所有尝试都失败
    return {
        "_error": "无法提取JSON",
        "_raw": text[:300],
        "_context": context
    }


# ============================================================================
# Layer 2: 异常追踪与重试
# ============================================================================

import time
import uuid
import traceback
from datetime import datetime
from functools import wraps
from typing import Callable, Any, TypeVar

T = TypeVar('T')


class ExceptionTracker:
    """异常追踪 - 记录、重试、降级"""
    
    # 异常日志存储 (JSONL 格式)
    _logs: list[dict] = []
    
    @staticmethod
    def log_exception(
        exc: Exception,
        operation: str,
        context: dict | None = None,
        exc_id: str | None = None
    ) -> str:
        """
        记录异常
        
        Args:
            exc: 异常对象
            operation: 操作名称 (如 "resume_parsing", "match_scoring")
            context: 上下文信息 (如 {"filename": "xxx.pdf"})
            exc_id: 异常ID (如果为None会自动生成)
        
        Returns:
            异常ID (用于追溯)
        """
        if exc_id is None:
            exc_id = str(uuid.uuid4())[:8]
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "exc_id": exc_id,
            "operation": operation,
            "exception_type": type(exc).__name__,
            "exception_msg": str(exc),
            "traceback": traceback.format_exc(),
            "context": context or {}
        }
        
        ExceptionTracker._logs.append(log_entry)
        logger.error(f"[{exc_id}] {operation} 失败: {type(exc).__name__}: {str(exc)}")
        
        return exc_id
    
    @staticmethod
    def handle_with_fallback(
        operation_name: str,
        func: Callable[..., T],
        fallback_value: T,
        *args,
        max_retries: int = 3,
        context: dict | None = None,
        **kwargs
    ) -> tuple[T, str | None]:
        """
        执行操作，异常时重试后降级
        
        Args:
            operation_name: 操作名称
            func: 可调用函数
            fallback_value: 降级值
            *args, **kwargs: 函数参数
            max_retries: 最大重试次数
            context: 上下文信息
        
        Returns:
            (结果, 异常ID或None)
        
        使用示例：
            result, exc_id = ExceptionTracker.handle_with_fallback(
                "resume_parsing",
                resume_agent.parse_resume,
                fallback_resume,
                masked_text,
                max_retries=2,
                context={"filename": "xxx.pdf"}
            )
        """
        exc_id = None
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(f"[{operation_name}] 尝试 {attempt}/{max_retries}")
                result = func(*args, **kwargs)
                
                if exc_id:
                    logger.info(f"[{exc_id}] 重试成功")
                
                return result, exc_id
            
            except Exception as e:
                if exc_id is None:
                    exc_id = ExceptionTracker.log_exception(
                        e, 
                        operation_name, 
                        context=context
                    )
                else:
                    logger.warning(f"[{exc_id}] 重试 {attempt} 失败: {type(e).__name__}")
                
                if attempt < max_retries:
                    # 指数退避: 0.5s, 1s, 2s
                    wait_time = 0.5 * (2 ** (attempt - 1))
                    logger.debug(f"等待 {wait_time:.1f}s 后重试...")
                    time.sleep(wait_time)
        
        # 所有重试都失败，降级
        logger.warning(
            f"[{exc_id}] {operation_name} 最终失败，返回降级值"
        )
        fallback_value["_is_fallback"] = True
        fallback_value["_exc_id"] = exc_id
        
        return fallback_value, exc_id
    
    @staticmethod
    def get_logs(
        operation_filter: str | None = None,
        exc_id_filter: str | None = None,
        limit: int | None = None
    ) -> list[dict]:
        """
        查询异常日志
        
        Args:
            operation_filter: 按操作名称过滤
            exc_id_filter: 按异常ID过滤
            limit: 返回最近N条
        
        Returns:
            日志列表
        """
        logs = ExceptionTracker._logs
        
        if operation_filter:
            logs = [l for l in logs if operation_filter in l.get("operation", "")]
        
        if exc_id_filter:
            logs = [l for l in logs if exc_id_filter in l.get("exc_id", "")]
        
        logs = sorted(logs, key=lambda x: x["timestamp"], reverse=True)
        
        if limit:
            logs = logs[:limit]
        
        return logs
    
    @staticmethod
    def clear_logs():
        """清空异常日志"""
        ExceptionTracker._logs.clear()
        logger.info("异常日志已清空")
    
    @staticmethod
    def export_logs_jsonl(filepath: str):
        """导出异常日志到 JSONL 文件"""
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            for log in ExceptionTracker._logs:
                f.write(json.dumps(log, ensure_ascii=False) + '\n')
        logger.info(f"异常日志已导出到 {filepath}")


# ============================================================================
# Layer 4: 公平性检查（FairnessChecker）
# 检测 LLM 推荐理由中是否包含与受保护属性相关的偏见词汇，
# 并对边缘分值区间的候选人标记人工复核。
# ============================================================================

class FairnessChecker:
    """
    公平性检查器：防止 AI 评分结果受性别/年龄/籍贯/婚姻状况等
    受保护属性影响，确保评分仅基于岗位相关能力。

    用法：
        report = FairnessChecker.check(match_result)
        if report["needs_human_review"]:
            ...
    """

    # 受保护属性关键词（出现在 recommendation / risks 中即触发警告）
    _BIAS_PATTERNS: dict[str, list[str]] = {
        "gender":   ["男性", "女性", "男生", "女生", "先生", "女士", "他", "她",
                     "male", "female", "mr.", "ms.", "mother", "father",
                     "pregnancy", "育儿", "生育", "哺乳"],
        "age":      ["年龄", "岁", "老", "老化", "年轻", "应届", "老员工",
                     "age", "too old", "too young", "experienced age"],
        "origin":   ["籍贯", "户籍", "老家", "农村", "外地", "本地",
                     "ethnicity", "nationality", "origin"],
        "marital":  ["婚姻", "已婚", "未婚", "离异", "有孩子", "孩子",
                     "marital", "married", "single", "children"],
        "politics": ["党员", "团员", "政治面貌", "political"],
    }

    # 人工复核分值边界（总分落在此区间需复核）
    _REVIEW_SCORE_RANGE = (55, 75)

    @classmethod
    def check(cls, match_result: dict, filename: str = "") -> dict:
        """
        对单份匹配结果进行公平性扫描。

        Returns:
            {
                "passed": bool,                   # True = 无偏见词
                "needs_human_review": bool,        # True = 建议人工复核
                "triggered_categories": list[str], # 触发的偏见类别
                "triggered_snippets": list[str],   # 触发的具体片段
                "review_reason": str,              # 复核原因说明
                "score": float,                    # 原始总分
            }
        """
        triggered_categories: list[str] = []
        triggered_snippets:   list[str] = []

        # 拼接待扫描文本（推荐理由 + 风险点）
        scan_text = " ".join([
            str(match_result.get("recommendation", "")),
            " ".join(str(r) for r in match_result.get("risks", [])),
            " ".join(str(q) for q in match_result.get("interview_questions", [])),
        ]).lower()

        for category, keywords in cls._BIAS_PATTERNS.items():
            for kw in keywords:
                if kw.lower() in scan_text:
                    if category not in triggered_categories:
                        triggered_categories.append(category)
                    # 提取上下文片段（前后 15 个字符）
                    idx = scan_text.find(kw.lower())
                    snippet = scan_text[max(0, idx - 15): idx + len(kw) + 15].strip()
                    triggered_snippets.append(f"[{category}] ...{snippet}...")

        score = float(match_result.get("total_score", 0))
        low, high = cls._REVIEW_SCORE_RANGE
        in_borderline = low <= score <= high

        reasons: list[str] = []
        if triggered_categories:
            reasons.append(f"推荐理由含受保护属性词汇：{', '.join(triggered_categories)}")
        if in_borderline:
            reasons.append(f"总分 {score:.1f} 处于边缘区间（{low}–{high}），建议人工复核避免边界歧视")

        needs_review = bool(triggered_categories) or in_borderline
        passed       = not bool(triggered_categories)

        report = {
            "passed":               passed,
            "needs_human_review":   needs_review,
            "triggered_categories": triggered_categories,
            "triggered_snippets":   triggered_snippets,
            "review_reason":        "；".join(reasons) if reasons else "无异常",
            "score":                score,
            "filename":             filename,
        }

        if not passed:
            logger.warning(
                f"[FairnessChecker] {filename or 'unknown'} 触发偏见词警告: "
                f"{triggered_categories} | 片段: {triggered_snippets[:2]}"
            )

        return report

    @classmethod
    def batch_summary(cls, fairness_reports: list[dict]) -> dict:
        """
        汇总批量公平性报告，供管理员审查。

        Returns:
            {
                "total": int,
                "passed": int,
                "needs_review": int,
                "bias_category_counts": dict,   # 各类偏见触发次数
                "review_candidates": list[str],  # 需复核的文件名
                "score_distribution": dict,      # 分段统计
            }
        """
        total   = len(fairness_reports)
        passed  = sum(1 for r in fairness_reports if r["passed"])
        reviews = [r for r in fairness_reports if r["needs_human_review"]]

        category_counts: dict[str, int] = {}
        for r in fairness_reports:
            for cat in r.get("triggered_categories", []):
                category_counts[cat] = category_counts.get(cat, 0) + 1

        # 分数段分布
        buckets = {"0-59": 0, "60-74": 0, "75-89": 0, "90-100": 0}
        for r in fairness_reports:
            s = r.get("score", 0)
            if s < 60:
                buckets["0-59"] += 1
            elif s < 75:
                buckets["60-74"] += 1
            elif s < 90:
                buckets["75-89"] += 1
            else:
                buckets["90-100"] += 1

        return {
            "total":                total,
            "passed":               passed,
            "needs_review":         len(reviews),
            "pass_rate":            round(passed / total * 100, 1) if total else 0,
            "bias_category_counts": category_counts,
            "review_candidates":    [r["filename"] for r in reviews],
            "score_distribution":   buckets,
        }
