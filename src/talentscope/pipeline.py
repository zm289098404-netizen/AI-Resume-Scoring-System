"""
Pipeline
========
4 Agent 串行编排：脱敏 → JD/简历解析 → 匹配 → 报告

支持两种简历来源：
- 临时上传（每份都跑解析 + 评分）
- 简历库（已解析，仅跑评分，速度快、零 LLM 成本）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Callable

from talentscope.agents import jd_agent, match_agent, report_agent, resume_agent
from talentscope.config_loader import get_config, get_output_dir
from talentscope.core.desensitizer import Desensitizer
from talentscope.core.language_detector import detect_languages
from talentscope.core.parser import parse_document
from talentscope.core.resume_library import LibraryRecord


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


# ---------------- 临时上传 ----------------
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
        try:
            raw_text = parse_document(r.file, filename=r.filename)
        except Exception as e:
            candidates.append({
                "file": r.filename, "error": f"解析失败: {e}",
                "department": "—",
                "resume": {}, "match": {"total_score": 0, "dimensions": {}},
            })
            continue

        languages = detect_languages(raw_text)
        masked = desens.mask(raw_text)
        resume = resume_agent.parse_resume(masked)
        resume["languages"] = languages
        _p(f"⚖️ [{i+1}/{n}] 评分 {r.filename}...", base_pct + 0.35 / max(n, 1))
        m = match_agent.match(jd, resume)
        candidates.append({
            "file": r.filename, "department": "—",
            "resume": resume, "match": m,
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
        resume = dict(rec.parsed)
        resume["languages"] = rec.languages
        m = match_agent.match(jd, resume)
        candidates.append({
            "file": rec.display_name,
            "library_id": rec.id,
            "department": rec.department,
            "resume": resume,
            "match": m,
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
