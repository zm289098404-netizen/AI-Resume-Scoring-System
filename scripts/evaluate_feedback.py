from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from talentscope.core import resume_library as lib


def build_markdown(summary: dict) -> str:
    lines = []
    lines.append("# TalentScope 反馈评测报告")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## 核心指标")
    lines.append(f"- 候选人总数：{summary['total_candidates']}")
    lines.append(f"- 已反馈人数：{summary['feedback_total']}")
    lines.append(f"- 反馈覆盖率：{summary['feedback_coverage']}%")
    lines.append(f"- 正向反馈率：{summary['positive_rate']}%")
    lines.append(f"- 负向反馈率：{summary['negative_rate']}%")
    lines.append(f"- 存疑占比：{summary['neutral_rate']}%")
    lines.append("")
    lines.append("## 状态分布")
    for status, count in summary.get("status_distribution", {}).items():
        lines.append(f"- {status}：{count}")
    lines.append("")
    lines.append("## 反馈明细")
    lines.append("")
    lines.append("| 姓名 | 部门 | 反馈状态 | 反馈时间 | 反馈说明 |")
    lines.append("|---|---|---|---|---|")
    for row in summary.get("records", []):
        note = (row.get("反馈说明") or "").replace("\n", " ").replace("|", "/")
        lines.append(
            f"| {row.get('姓名', '')} | {row.get('部门', '')} | {row.get('反馈状态', '')} | {row.get('反馈时间', '') or '—'} | {note or '—'} |"
        )
    return "\n".join(lines)


def main() -> None:
    summary = lib.summarize_feedback()
    out_dir = ROOT / "data" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    report_path = out_dir / f"feedback-evaluation-{stamp}.md"
    json_path = out_dir / f"feedback-evaluation-{stamp}.json"

    report_md = build_markdown(summary)
    report_path.write_text(report_md, encoding="utf-8")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"反馈评测报告已生成: {report_path}")
    print(f"反馈评测 JSON 已生成: {json_path}")
    print(f"反馈覆盖率: {summary['feedback_coverage']}%")
    print(f"正向反馈率: {summary['positive_rate']}%")


if __name__ == "__main__":
    main()