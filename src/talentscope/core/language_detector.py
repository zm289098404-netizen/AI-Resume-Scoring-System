"""
语言能力检测
============
从简历文本中粗略提取候选人的外语技能，输出 [{"name": "英语", "level": "流利"}, ...]
"""
from __future__ import annotations

import re

from talentscope.config_loader import get_languages


def detect_languages(text: str) -> list[dict]:
    """从简历文本里检测外语技能"""
    if not text:
        return []
    data = get_languages()
    languages = data["languages"]
    aliases = data.get("aliases", {})
    levels = data.get("levels", ["入门", "日常", "流利", "母语"])

    text_lower = text.lower()
    found: dict[str, str] = {}  # name -> level

    # 1) 检查每个标准语言名
    for lang in languages:
        name = lang["name"]
        if name in text or name.lower() in text_lower:
            found[name] = _infer_level(text, name, levels)

    # 2) 检查别名（CET-6 → 英语 流利）
    for alias, std_name in aliases.items():
        if alias.lower() in text_lower and std_name not in found:
            lvl = _level_from_cert(alias)
            found[std_name] = lvl or _infer_level(text, std_name, levels)

    return [{"name": k, "level": v} for k, v in found.items()]


def _infer_level(text: str, lang_name: str, levels: list[str]) -> str:
    """在 lang_name 出现位置附近搜索水平描述词"""
    idx = text.find(lang_name)
    if idx < 0:
        idx = text.lower().find(lang_name.lower())
    window = text[max(0, idx - 30): idx + 40] if idx >= 0 else text[:200]
    for kw in ["母语", "精通", "流利", "熟练", "良好", "日常", "入门"]:
        if kw in window:
            if kw in ("母语",):
                return "母语"
            if kw in ("精通", "流利", "熟练"):
                return "流利"
            if kw in ("良好", "日常"):
                return "日常"
            return "入门"
    return "日常"  # 默认


def _level_from_cert(alias: str) -> str | None:
    """从证书别名推断等级"""
    a = alias.lower()
    if a in ("cet-6", "cet6", "六级", "ielts", "toefl", "雅思", "托福", "n1"):
        return "流利"
    if a in ("cet-4", "cet4", "四级", "n2"):
        return "日常"
    return None


# ---------------- 匹配评分辅助 ----------------
LEVEL_SCORE = {"入门": 25, "日常": 60, "流利": 90, "母语": 100}


def score_languages(required: list[dict], candidate: list[dict]) -> tuple[float, list[str], list[str]]:
    """
    required: [{"name": "英语", "min_level": "流利"}, ...]   UI 上多选生成
    candidate: [{"name": "英语", "level": "流利"}, ...]

    返回: (score 0-100, matched_names, missing_names)
    """
    if not required:
        return 100.0, [], []
    cand_map = {c["name"]: c.get("level", "日常") for c in candidate or []}
    matched, missing = [], []
    total, n = 0, len(required)
    for req in required:
        name = req["name"]
        min_lvl = req.get("min_level", "日常")
        min_score = LEVEL_SCORE.get(min_lvl, 60)
        if name in cand_map:
            cv_score = LEVEL_SCORE.get(cand_map[name], 60)
            if cv_score >= min_score:
                matched.append(f"{name}({cand_map[name]})")
                total += 100
            else:
                matched.append(f"{name}({cand_map[name]} 低于要求)")
                total += int(cv_score / min_score * 70)
        else:
            missing.append(f"{name}({min_lvl}+)")
            total += 0
    return round(total / n, 1), matched, missing
