from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from talentscope.config_loader import get_job_templates, get_languages
from talentscope.core import resume_library as lib


def estimate_fit(record: lib.LibraryRecord, template: dict, lang_levels: list[str]) -> dict:
    parsed = record.parsed or {}
    must_skills = {s.lower() for s in template.get("must_have_skills", [])}
    cv_skills = {s.lower() for s in parsed.get("skills", [])}
    matched = must_skills & cv_skills
    skill_rate = len(matched) / len(must_skills) if must_skills else 1.0

    level_idx = {name: i for i, name in enumerate(lang_levels)}
    cv_lang = {x.get("name"): x.get("level", "") for x in (record.languages or []) if isinstance(x, dict)}
    lang_total = len(template.get("required_languages", []))
    lang_hit = 0
    for req in template.get("required_languages", []):
        name = req.get("name")
        req_lvl = req.get("min_level", "日常")
        cv_lvl = cv_lang.get(name, "")
        if name in cv_lang and level_idx.get(cv_lvl, -1) >= level_idx.get(req_lvl, -1):
            lang_hit += 1
    lang_rate = lang_hit / lang_total if lang_total else 1.0

    req_exp = float(template.get("experience_years", 0) or 0)
    cv_exp = float(parsed.get("experience_years", 0) or 0)
    exp_rate = min(cv_exp / req_exp, 1.0) if req_exp > 0 else 1.0
    fit_score = round((skill_rate * 0.6 + lang_rate * 0.2 + exp_rate * 0.2) * 100, 1)

    return {
        "fit_score": fit_score,
        "skill_rate": round(skill_rate * 100, 1),
        "lang_rate": round(lang_rate * 100, 1),
        "exp_rate": round(exp_rate * 100, 1),
    }


def main() -> None:
    templates = get_job_templates().get("templates", [])
    lang_levels = get_languages().get("levels", ["入门", "日常", "流利", "母语"])
    records = lib.list_records()

    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "templates": [],
    }

    for tpl in templates:
        scored = []
        for rec in records:
            fit = estimate_fit(rec, tpl, lang_levels)
            scored.append({
                "candidate": rec.display_name,
                "department": rec.department,
                **fit,
            })
        scored.sort(key=lambda x: x["fit_score"], reverse=True)
        high_fit = [x for x in scored if x["fit_score"] >= 75]
        medium_fit = [x for x in scored if 60 <= x["fit_score"] < 75]
        risk = "低"
        if len(high_fit) < 2:
            risk = "高" if len(high_fit) == 0 else "中"

        result["templates"].append(
            {
                "id": tpl.get("id"),
                "name": tpl.get("name"),
                "version": tpl.get("version"),
                "high_fit_count": len(high_fit),
                "medium_fit_count": len(medium_fit),
                "supply_risk": risk,
                "top_candidates": scored[:5],
            }
        )

    out_dir = ROOT / "data" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"template-regression-{stamp}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"模板回归检查结果已生成: {out_path}")
    for item in result["templates"]:
        print(f"- {item['name']}: 高匹配 {item['high_fit_count']}，供给风险 {item['supply_risk']}")


if __name__ == "__main__":
    main()
