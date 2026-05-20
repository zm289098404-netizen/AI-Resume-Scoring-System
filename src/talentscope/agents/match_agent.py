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
  "risks": ["风险点"]
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

    # 兜底字段
    llm_result.setdefault("recommendation", "—")
    llm_result.setdefault("risks", [])
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
    }
