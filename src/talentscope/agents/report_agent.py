"""
报告生成 Agent
==============
把若干个候选人的匹配结果聚合为 Markdown 报告。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def build_report(jd: dict, results: list[dict], output_path: Path | None = None) -> str:
    """results: [{"file": "xxx.pdf", "resume": {...}, "match": {...}}, ...]"""
    sorted_results = sorted(results, key=lambda r: r["match"]["total_score"], reverse=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append(f"# 📊 简历匹配评分报告")
    lines.append(f"\n> 生成时间：{now}　·　候选人数量：{len(sorted_results)}")
    lines.append(f"\n## 一、岗位概览")
    lines.append(f"- **岗位名称**：{jd.get('title', '未命名')}")
    lines.append(f"- **经验要求**：{jd.get('experience_years', 0)} 年+")
    lines.append(f"- **学历要求**：{jd.get('education', '不限')}")
    req_skills = [s["name"] for s in jd.get("hard_skills", []) if s.get("required", True)]
    opt_skills = [s["name"] for s in jd.get("hard_skills", []) if not s.get("required", True)]
    if req_skills:
        lines.append(f"- **必备技能**：{', '.join(req_skills)}")
    if opt_skills:
        lines.append(f"- **加分技能**：{', '.join(opt_skills)}")

    lines.append(f"\n## 二、Top 排名")
    lines.append("\n| 排名 | 候选人 | 总分 | 硬技能 | 经验 | 软技能 | 学历 | 文件 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(sorted_results[:20], 1):
        m = r["match"]
        d = m["dimensions"]
        cid = r["resume"].get("candidate_id", "—")
        lines.append(
            f"| {i} | {cid} | **{m['total_score']}** | "
            f"{d['hard_skill']} | {d['experience']} | {d['soft_skill']} | {d['education']} | {r['file']} |"
        )

    lines.append(f"\n## 三、Top 5 详细推荐")
    for i, r in enumerate(sorted_results[:5], 1):
        m = r["match"]
        res = r["resume"]
        lines.append(f"\n### 🏅 第 {i} 名 · {res.get('candidate_id')}（总分 {m['total_score']}）")
        lines.append(f"- **文件**：{r['file']}")
        lines.append(f"- **经验**：{res.get('experience_years', 0)} 年　·　**学历**：{res.get('education', '—')}")
        if m.get("matched_skills"):
            lines.append(f"- ✅ **匹配技能**：{', '.join(m['matched_skills'])}")
        if m.get("missing_skills"):
            lines.append(f"- ❌ **缺失技能**：{', '.join(m['missing_skills'])}")
        if res.get("highlights"):
            lines.append(f"- 🌟 **亮点**：{'；'.join(res['highlights'])}")
        if m.get("risks"):
            lines.append(f"- ⚠️ **风险**：{'；'.join(m['risks'])}")
        lines.append(f"- 💡 **推荐理由**：{m.get('recommendation', '—')}")

    lines.append(f"\n---")
    lines.append(f"\n*报告由 TalentScope 自动生成。本报告供 HR 内部参考，不构成最终录用决策。*")

    md = "\n".join(lines)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md, encoding="utf-8")
    return md
