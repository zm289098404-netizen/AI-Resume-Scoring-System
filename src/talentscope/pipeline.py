"""
Pipeline
========
4 Agent 串行编排：脱敏 → JD/简历解析 → 匹配 → 报告

支持两种简历来源：
- 临时上传（每份都跑解析 + 评分）
- 简历库（已解析，仅跑评分，速度快、零 LLM 成本）

Phase 2: 添加了异常处理，单个简历失败不会停止整批处理
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Callable

from talentscope.agents import jd_agent, match_agent, report_agent, resume_agent
from talentscope.config_loader import get_config, get_output_dir
from talentscope.core.desensitizer import Desensitizer
from talentscope.core.language_detector import detect_languages
from talentscope.core.parser import parse_document
from talentscope.core.resume_library import LibraryRecord
from talentscope.core.stability_framework import (
    ExceptionTracker,
    safe_json_loads,
)

logger = logging.getLogger(__name__)


@dataclass
class ResumeInput:
    filename: str
    file: IO[bytes] | Path | str


@dataclass
class PipelineResult:
    jd: dict
    candidates: list[dict] = field(default_factory=list)
    report_md: str = ""
    report_path: Path | None = None


def _build_fallback_resume(filename: str, error: str, exc_id: str) -> dict:
    """构造降级的简历解析结果"""
    return {
        "name": "—",
        "email": "",
        "phone": "",
        "location": "—",
        "summary": f"[解析失败] {error}",
        "experience_years": 0,
        "education": "未知",
        "skills": [],
        "highlights": [],
        "languages": [],
        "_is_fallback": True,
        "_exc_id": exc_id,
    }


def _build_fallback_match(filename: str, error: str, exc_id: str) -> dict:
    """构造降级的匹配结果"""
    return {
        "total_score": 0,
        "dimensions": {
            "hard_skill": 0,
            "experience": 0,
            "soft_skill": 0,
            "education": 0
        },
        "matched_skills": [],
        "missing_skills": [],
        "recommendation": (
            f"评分过程中出现问题，已自动降级。"
            f"请重新上传简历或联系管理员。"
            f"(异常ID: {exc_id})"
        ),
        "risks": [f"处理异常: {error}"],
        "interview_questions": ["请与管理员联系获取帮助"],
        "confidence": 0.0,
        "_is_fallback": True,
        "_exc_id": exc_id,
    }


# ============================================================================
# 内部辅助 - 降级处理
# ============================================================================
def run(
    jd_text: str,
    resumes: list[ResumeInput],
    required_skill_filter: list[str] | None = None,
    required_languages: list[dict] | None = None,
    progress_cb: Callable[[str, float], None] | None = None,
) -> PipelineResult:
    cfg = get_config()
    desens = Desensitizer(
        enabled=cfg["desensitize"]["enabled"],
        fields=cfg["desensitize"]["fields"],
    )

    def _p(msg: str, pct: float):
        if progress_cb:
            progress_cb(msg, pct)

    _p("🔒 JD 脱敏中...", 0.05)
    jd_masked = desens.mask(jd_text)
    _p("📋 JD 解析中...", 0.15)
    jd = jd_agent.parse_jd(jd_masked)
    _apply_filters_to_jd(jd, required_skill_filter, required_languages)

    candidates = []
    n = len(resumes)
    for i, r in enumerate(resumes):
        base_pct = 0.2 + 0.7 * (i / max(n, 1))
        _p(f"📄 [{i+1}/{n}] 解析 {r.filename}...", base_pct)
        
        # ✅ Phase 2: 文档解析异常处理
        raw_text, parse_exc_id = ExceptionTracker.handle_with_fallback(
            "document_parsing",
            parse_document,
            "",  # 降级值：空字符串
            r.file,
            filename=r.filename,
            max_retries=2,
            context={"filename": r.filename, "stage": "document_parsing"}
        )
        
        if parse_exc_id:
            # 解析失败
            logger.warning(f"[{parse_exc_id}] 简历 {r.filename} 文档解析失败")
            candidates.append({
                "file": r.filename,
                "department": "—",
                "resume": _build_fallback_resume(r.filename, "文档解析失败", parse_exc_id),
                "match": _build_fallback_match(r.filename, "文档解析失败", parse_exc_id),
                "_exc_id": parse_exc_id,
            })
            continue

        languages = detect_languages(raw_text)
        masked = desens.mask(raw_text)
        
        # ✅ Phase 2: 简历解析异常处理
        resume, resume_exc_id = ExceptionTracker.handle_with_fallback(
            "resume_parsing",
            resume_agent.parse_resume,
            _build_fallback_resume(r.filename, "简历解析失败", "unknown"),
            masked,
            max_retries=2,
            context={"filename": r.filename, "stage": "resume_parsing"}
        )
        
        if resume_exc_id:
            resume["_exc_id"] = resume_exc_id
            logger.warning(f"[{resume_exc_id}] 简历 {r.filename} 解析失败，已降级")
        
        resume["languages"] = languages
        
        # ✅ Phase 2: 匹配评分异常处理
        match_result, match_exc_id = ExceptionTracker.handle_with_fallback(
            "match_scoring",
            match_agent.match,
            _build_fallback_match(r.filename, "评分失败", "unknown"),
            jd,
            resume,
            max_retries=2,
            context={"filename": r.filename, "stage": "match_scoring"}
        )
        
        if match_exc_id:
            match_result["_exc_id"] = match_exc_id
            logger.warning(f"[{match_exc_id}] 简历 {r.filename} 评分失败，已降级")
        
        candidates.append({
            "file": r.filename,
            "department": "—",
            "resume": resume,
            "match": match_result,
            "_exc_id": match_exc_id or (resume.get("_exc_id") if not match_exc_id else None),
        })

    return _finalize(jd, candidates, _p)


# ---------------- 从简历库匹配 ----------------
def run_from_library(
    jd_text: str,
    records: list[LibraryRecord],
    required_skill_filter: list[str] | None = None,
    required_languages: list[dict] | None = None,
    progress_cb: Callable[[str, float], None] | None = None,
) -> PipelineResult:
    """从简历库匹配（不重复跑简历 LLM，仅跑 JD 解析 + 评分）"""
    cfg = get_config()
    desens = Desensitizer(
        enabled=cfg["desensitize"]["enabled"],
        fields=cfg["desensitize"]["fields"],
    )

    def _p(msg: str, pct: float):
        if progress_cb:
            progress_cb(msg, pct)

    _p("📋 JD 解析中...", 0.15)
    jd_masked = desens.mask(jd_text)
    jd = jd_agent.parse_jd(jd_masked)
    _apply_filters_to_jd(jd, required_skill_filter, required_languages)

    candidates = []
    n = len(records)
    for i, rec in enumerate(records):
        pct = 0.2 + 0.7 * ((i + 1) / max(n, 1))
        _p(f"⚖️ [{i+1}/{n}] 评分 {rec.display_name}...", pct)
        
        # ✅ Phase 2: 匹配评分异常处理（从库加载的简历）
        resume = dict(rec.parsed)
        resume["languages"] = rec.languages
        
        match_result, match_exc_id = ExceptionTracker.handle_with_fallback(
            "match_scoring_from_library",
            match_agent.match,
            _build_fallback_match(rec.display_name, "评分失败", "unknown"),
            jd,
            resume,
            max_retries=2,
            context={"library_id": rec.id, "display_name": rec.display_name}
        )
        
        if match_exc_id:
            match_result["_exc_id"] = match_exc_id
            logger.warning(f"[{match_exc_id}] 库简历 {rec.display_name} 评分失败，已降级")
        
        candidates.append({
            "file": rec.display_name,
            "library_id": rec.id,
            "department": rec.department,
            "resume": resume,
            "match": match_result,
            "_exc_id": match_exc_id,
        })

    return _finalize(jd, candidates, _p)


# ---------------- 内部辅助 ----------------
def _apply_filters_to_jd(
    jd: dict,
    required_skills: list[str] | None,
    required_languages: list[dict] | None,
) -> None:
    if required_skills:
        existing = {s["name"].lower() for s in jd.get("hard_skills", [])}
        for s in required_skills:
            if s.lower() not in existing:
                jd.setdefault("hard_skills", []).append(
                    {"name": s, "required": True, "weight": 1.0}
                )
            else:
                for hs in jd["hard_skills"]:
                    if hs["name"].lower() == s.lower():
                        hs["required"] = True

    if required_languages:
        jd["required_languages"] = required_languages
    else:
        jd.setdefault("required_languages", [])


def _finalize(jd, candidates, _p) -> PipelineResult:
    _p("📊 生成报告...", 0.95)
    out_dir = get_output_dir()
    from datetime import datetime
    fname = f"report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    out_path = out_dir / fname
    report_md = report_agent.build_report(jd, candidates, output_path=out_path)
    _p("✅ 完成", 1.0)
    return PipelineResult(jd=jd, candidates=candidates, report_md=report_md, report_path=out_path)
