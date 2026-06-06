"""
匹配评分 Agent
==============
输入：解析后的 JD + 解析后的简历
输出：多维评分 + 推荐理由

注意：分数计算同时支持两种模式：
- LLM 评分（推荐理由由 LLM 生成）
- 本地加权（确定性，可复现）

两者结果合并：分数取本地加权，理由取 LLM 生成。
"""
from __future__ import annotations

import json
from typing import Any

from talentscope.config_loader import get_config
from talentscope.core.language_detector import score_languages
from talentscope.core.llm_client import get_llm_client

SYSTEM_PROMPT = """你是一名资深技术招聘专家 (匹配评分 Agent)。
任务：根据 JD 和简历的结构化数据，给出匹配评分和推荐理由。

输入是 JSON：{"jd": {...}, "resume": {...}}

返回 JSON：
{
  "total_score": 85.5,
  "dimensions": {
    "hard_skill": 88,
    "experience": 90,
    "soft_skill": 75,
    "education": 80
  },
  "matched_skills": ["匹配的技能"],
  "missing_skills": ["缺失的关键技能"],
  "recommendation": "一段话推荐理由，2-3 句",
    "risks": ["风险点"],
    "interview_questions": ["建议面试追问 1", "建议面试追问 2"]
}

打分规则：
- hard_skill: 关键技能命中率（必备技能权重高）
- experience: 年限匹配度（不足扣分，过度匹配也轻微扣分）
- soft_skill: 软技能描述匹配度
- education: 学历是否达标
- total_score: 加权后总分，0-100

严格只输出 JSON。
"""


def match(jd: dict, resume: dict) -> dict:
    client = get_llm_client()
    payload = json.dumps({"jd": jd, "resume": resume}, ensure_ascii=False)
    llm_result = client.chat_json(SYSTEM_PROMPT, payload)

    # 用本地加权确保分数稳定（覆盖 LLM 分数，但保留推荐理由）
    local = _local_score(jd, resume)
    llm_result["total_score"] = local["total_score"]
    llm_result["dimensions"] = local["dimensions"]
    llm_result["matched_skills"] = local["matched_skills"]
    llm_result["missing_skills"] = local["missing_skills"]
    llm_result["matched_languages"] = local["matched_languages"]
    llm_result["missing_languages"] = local["missing_languages"]
    llm_result["evidence"] = local["evidence"]
    llm_result["evidence_summary"] = local["evidence_summary"]
    llm_result["follow_up_checks"] = local["follow_up_checks"]
    llm_result["confidence"] = local["confidence"]

    # 兜底字段
    llm_result.setdefault("recommendation", "—")
    llm_result.setdefault("risks", [])
    llm_result.setdefault(
        "interview_questions",
        _build_interview_questions(jd, resume, local),
    )
    return llm_result


def _local_score(jd: dict, resume: dict) -> dict[str, Any]:
    """确定性的本地打分逻辑，不依赖 LLM"""
    cfg = get_config()["scoring"]["weights"]

    jd_skills = jd.get("hard_skills", [])
    required_skills = {s["name"].lower() for s in jd_skills if s.get("required", True)}
    optional_skills = {s["name"].lower() for s in jd_skills if not s.get("required", True)}
    resume_skills = {s.lower() for s in resume.get("skills", [])}

    matched_req = required_skills & resume_skills
    matched_opt = optional_skills & resume_skills
    missing = required_skills - resume_skills
    all_matched = matched_req | matched_opt

    # 硬技能得分（必备 70% 权重 + 加分 30%）
    if required_skills:
        req_rate = len(matched_req) / len(required_skills)
    else:
        req_rate = 1.0
    opt_rate = len(matched_opt) / max(len(optional_skills), 1) if optional_skills else 0.0
    hard_score = (req_rate * 0.7 + opt_rate * 0.3) * 100

    # 经验得分
    jd_years = jd.get("experience_years", 0) or 0
    cv_years = resume.get("experience_years", 0) or 0
    if jd_years == 0:
        exp_score = 80.0
    elif cv_years >= jd_years:
        # 超过太多反而轻微扣分
        ratio = min(cv_years / jd_years, 2.0)
        exp_score = 100 - max(0, (ratio - 1.5)) * 20
    else:
        exp_score = (cv_years / jd_years) * 100

    # 软技能（简易匹配）
    jd_soft = {s.lower() for s in jd.get("soft_skills", [])}
    cv_soft_text = " ".join(resume.get("highlights", [])).lower()
    soft_hits = sum(1 for s in jd_soft if s in cv_soft_text)
    soft_score = 60 + soft_hits * 10 if jd_soft else 75
    soft_score = min(soft_score, 100)

    # 学历
    edu_rank = {"博士": 4, "硕士": 3, "本科": 2, "大专": 1, "未知": 1, "不限": 2}
    jd_edu = jd.get("education", "不限")
    cv_edu = resume.get("education", "未知")
    jd_level = max([v for k, v in edu_rank.items() if k in jd_edu] or [2])
    cv_level = max([v for k, v in edu_rank.items() if k in cv_edu] or [1])
    if cv_level >= jd_level:
        edu_score = 90.0
    elif cv_level == jd_level - 1:
        edu_score = 70.0
    else:
        edu_score = 50.0

    # 语言
    jd_langs = jd.get("required_languages", [])  # [{"name":..,"min_level":..}]
    cv_langs = resume.get("languages", [])
    lang_score, lang_matched, lang_missing = score_languages(jd_langs, cv_langs)
    soft_hits_list = sorted(s for s in jd_soft if s in cv_soft_text)
    evidence_summary = _build_evidence_summary(
        required_skills=required_skills,
        matched_req=matched_req,
        optional_skills=optional_skills,
        matched_opt=matched_opt,
        jd_years=jd_years,
        cv_years=cv_years,
        jd_edu=jd_edu,
        cv_edu=cv_edu,
        cv_level=cv_level,
        jd_level=jd_level,
        soft_hits=soft_hits_list,
        lang_matched=lang_matched,
        jd_langs=jd_langs,
    )
    follow_up_checks = _build_follow_up_checks(
        missing_skills=missing,
        jd_years=jd_years,
        cv_years=cv_years,
        lang_missing=lang_missing,
        cv_level=cv_level,
        jd_level=jd_level,
        highlights=resume.get("highlights", []),
    )
    confidence = _estimate_confidence(
        resume=resume,
        required_skills=required_skills,
        matched_req=matched_req,
        jd_langs=jd_langs,
        lang_missing=lang_missing,
    )

    total = (
        hard_score * cfg["hard_skill"]
        + exp_score * cfg["experience"]
        + soft_score * cfg["soft_skill"]
        + edu_score * cfg["education"]
        + lang_score * cfg.get("language", 0)
    )

    return {
        "total_score": round(total, 1),
        "dimensions": {
            "hard_skill": round(hard_score, 1),
            "experience": round(exp_score, 1),
            "soft_skill": round(soft_score, 1),
            "education": round(edu_score, 1),
            "language": round(lang_score, 1),
        },
        "matched_skills": sorted(all_matched),
        "missing_skills": sorted(missing),
        "matched_languages": lang_matched,
        "missing_languages": lang_missing,
        "evidence": {
            "required_skill_coverage": {
                "matched": len(matched_req),
                "total": len(required_skills),
                "rate": round(req_rate * 100, 1),
            },
            "optional_skill_coverage": {
                "matched": len(matched_opt),
                "total": len(optional_skills),
                "rate": round(opt_rate * 100, 1) if optional_skills else 0.0,
            },
            "experience": {
                "required_years": jd_years,
                "candidate_years": cv_years,
                "gap_years": round(cv_years - jd_years, 1),
            },
            "education": {
                "required": jd_edu,
                "candidate": cv_edu,
                "meets_requirement": cv_level >= jd_level,
            },
            "soft_skill_hits": soft_hits_list,
            "highlight_evidence": resume.get("highlights", [])[:3],
        },
        "evidence_summary": evidence_summary,
        "follow_up_checks": follow_up_checks,
        "confidence": confidence,
    }


def _build_evidence_summary(
    *,
    required_skills: set[str],
    matched_req: set[str],
    optional_skills: set[str],
    matched_opt: set[str],
    jd_years: float,
    cv_years: float,
    jd_edu: str,
    cv_edu: str,
    cv_level: int,
    jd_level: int,
    soft_hits: list[str],
    lang_matched: list[dict],
    jd_langs: list[dict],
) -> list[str]:
    lines: list[str] = []
    if required_skills:
        lines.append(
            f"命中必备技能 {len(matched_req)}/{len(required_skills)}，覆盖率 {round(len(matched_req) / len(required_skills) * 100, 1)}%"
        )
    if optional_skills:
        lines.append(f"命中加分技能 {len(matched_opt)}/{len(optional_skills)}")
    if jd_years:
        if cv_years >= jd_years:
            lines.append(f"经验满足要求：候选人 {cv_years} 年，岗位要求 {jd_years} 年+")
        else:
            lines.append(f"经验存在缺口：候选人 {cv_years} 年，低于岗位要求 {jd_years} 年+")
    lines.append(
        f"学历对比：候选人 {cv_edu or '未知'}，岗位要求 {jd_edu or '不限'}，{'已达标' if cv_level >= jd_level else '需人工确认'}"
    )
    if jd_langs:
        lines.append(f"语言满足 {len(lang_matched)}/{len(jd_langs)} 项")
    if soft_hits:
        lines.append(f"软技能证据：{', '.join(soft_hits[:3])}")
    return lines


def _build_follow_up_checks(
    *,
    missing_skills: set[str],
    jd_years: float,
    cv_years: float,
    lang_missing: list[dict],
    cv_level: int,
    jd_level: int,
    highlights: list[str],
) -> list[str]:
    checks: list[str] = []
    if missing_skills:
        checks.append(f"核验缺失技能是否具备实际项目经验：{', '.join(sorted(missing_skills)[:3])}")
    if jd_years and cv_years < jd_years:
        checks.append(f"进一步确认候选人是否有可等价折算的项目深度，以弥补 {round(jd_years - cv_years, 1)} 年经验缺口")
    if lang_missing:
        names = []
        for item in lang_missing[:3]:
            if isinstance(item, dict):
                names.append(f"{item.get('name', '?')}({item.get('min_level', '')})")
            else:
                names.append(str(item))
        checks.append(f"语言能力需要面试复核：{', '.join(names)}")
    if cv_level < jd_level:
        checks.append("学历未完全达标，建议确认岗位是否允许以经验和项目成果替代")
    if len(highlights) < 2:
        checks.append("简历亮点描述较少，建议让候选人补充项目背景、职责和量化结果")
    return checks or ["整体匹配度较稳定，建议围绕关键项目深挖真实性与实际贡献。"]


def _build_interview_questions(jd: dict, resume: dict, local: dict[str, Any]) -> list[str]:
    questions: list[str] = []
    missing_skills = local.get("missing_skills", [])
    for skill in missing_skills[:2]:
        questions.append(f"你在过往项目中是否实际使用过 {skill}？请举一个可量化成果的案例。")

    gap_years = local.get("evidence", {}).get("experience", {}).get("gap_years", 0)
    if isinstance(gap_years, (int, float)) and gap_years < 0:
        questions.append("你的工作年限略低于岗位要求，能否结合一个高复杂度项目说明你承担的关键职责与难点？")

    for highlight in resume.get("highlights", [])[:2]:
        questions.append(f"简历中提到“{highlight}”，请展开说明你的个人贡献、指标结果和复盘。")

    if jd.get("required_languages"):
        questions.append("请用岗位要求的语言简要介绍一个你最熟悉的项目，验证实际沟通与表达能力。")

    return questions[:4] or ["请挑选一段最能体现岗位匹配度的经历，说明场景、动作、结果和个人贡献。"]


def _estimate_confidence(
    *,
    resume: dict,
    required_skills: set[str],
    matched_req: set[str],
    jd_langs: list[dict],
    lang_missing: list[dict],
) -> float:
    score = 45.0
    if resume.get("highlights"):
        score += 15.0
    if resume.get("experience_years"):
        score += 10.0
    if resume.get("education"):
        score += 5.0
    if required_skills:
        score += 15.0 * (len(matched_req) / len(required_skills))
    else:
        score += 10.0
    if jd_langs:
        score += 10.0 * (1 - len(lang_missing) / max(len(jd_langs), 1))
    return round(max(0.0, min(score, 100.0)), 1)
