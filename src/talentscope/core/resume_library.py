"""
简历库管理
==========
持久化存储已经解析过的简历，下次匹配时可直接复用，不必重复跑 LLM。

每份简历 = data/resume_library/<id>.json
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import IO

from talentscope.agents.resume_agent import parse_resume
from talentscope.config_loader import get_library_dir
from talentscope.core.desensitizer import Desensitizer
from talentscope.core.language_detector import detect_languages
from talentscope.core.parser import parse_document


@dataclass
class LibraryRecord:
    id: str
    display_name: str          # 候选人显示名（可手填或文件名）
    department: str             # 所属部门 / BU
    source_file: str            # 原始文件名
    imported_at: str            # ISO 时间戳
    parsed: dict                # resume_agent 输出
    languages: list[dict] = field(default_factory=list)  # [{"name":..,"level":..}]
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    feedback_status: str = "未反馈"
    feedback_note: str = ""
    feedback_updated_at: str = ""
    feedback_history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LibraryRecord":
        return cls(
            id=d.get("id", ""),
            display_name=d.get("display_name", "—"),
            department=d.get("department", "未分配"),
            source_file=d.get("source_file", ""),
            imported_at=d.get("imported_at", ""),
            parsed=d.get("parsed", {}),
            languages=d.get("languages", []),
            tags=d.get("tags", []),
            notes=d.get("notes", ""),
            feedback_status=d.get("feedback_status", "未反馈"),
            feedback_note=d.get("feedback_note", ""),
            feedback_updated_at=d.get("feedback_updated_at", ""),
            feedback_history=d.get("feedback_history", []),
        )


# ---------------- CRUD ----------------
def _path_for(record_id: str) -> Path:
    return get_library_dir() / f"{record_id}.json"


def list_records() -> list[LibraryRecord]:
    out: list[LibraryRecord] = []
    for p in sorted(get_library_dir().glob("*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                out.append(LibraryRecord.from_dict(json.load(f)))
        except Exception:
            continue
    return out


def get_record(record_id: str) -> LibraryRecord | None:
    p = _path_for(record_id)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return LibraryRecord.from_dict(json.load(f))


def save_record(rec: LibraryRecord) -> None:
    p = _path_for(rec.id)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(rec.to_dict(), f, ensure_ascii=False, indent=2)


def delete_record(record_id: str) -> bool:
    p = _path_for(record_id)
    if p.exists():
        p.unlink()
        return True
    return False


def update_record(record_id: str, **fields) -> LibraryRecord | None:
    rec = get_record(record_id)
    if rec is None:
        return None
    for k, v in fields.items():
        if hasattr(rec, k):
            setattr(rec, k, v)
    save_record(rec)
    return rec


def update_feedback(record_id: str, status: str, note: str = "") -> LibraryRecord | None:
    rec = get_record(record_id)
    if rec is None:
        return None

    now = datetime.now().isoformat(timespec="seconds")
    rec.feedback_status = status
    rec.feedback_note = note
    rec.feedback_updated_at = now
    rec.feedback_history.append({
        "status": status,
        "note": note,
        "updated_at": now,
    })
    save_record(rec)
    return rec


# ---------------- 导入 ----------------
def import_resume(
    file: IO[bytes] | str | Path,
    filename: str | None = None,
    department: str = "未分配",
    display_name: str = "",
    desensitize_enabled: bool = True,
) -> LibraryRecord:
    """解析并入库一份简历。

    返回新创建的记录。LLM 只会在导入时调用一次，后续匹配 0 LLM 成本。
    """
    fname = filename or (Path(file).name if isinstance(file, (str, Path)) else "uploaded")
    raw_text = parse_document(file, filename=fname)

    # 检测语言（在脱敏前做，因为语言关键字可能包含人名 / 学校名）
    languages = detect_languages(raw_text)

    # 脱敏 → LLM 解析
    desens = Desensitizer(enabled=desensitize_enabled)
    masked = desens.mask(raw_text)
    parsed = parse_resume(masked)

    rec = LibraryRecord(
        id=f"lib-{uuid.uuid4().hex[:8]}",
        display_name=display_name or fname,
        department=department,
        source_file=fname,
        imported_at=datetime.now().isoformat(timespec="seconds"),
        parsed=parsed,
        languages=languages,
    )
    save_record(rec)
    return rec


# ---------------- 过滤 ----------------
def filter_records(
    departments: list[str] | None = None,
    must_languages: list[str] | None = None,
    keyword: str = "",
) -> list[LibraryRecord]:
    recs = list_records()
    if departments:
        dset = set(departments)
        recs = [r for r in recs if r.department in dset]
    if must_languages:
        lset = set(must_languages)
        recs = [r for r in recs if lset.issubset({lng["name"] for lng in r.languages})]
    if keyword:
        kw = keyword.lower()
        recs = [
            r for r in recs
            if kw in r.display_name.lower()
            or kw in r.department.lower()
            or kw in r.notes.lower()
            or kw in r.feedback_note.lower()
            or kw in json.dumps(r.parsed, ensure_ascii=False).lower()
        ]
    return recs


def stats() -> dict:
    recs = list_records()
    dept_count: dict[str, int] = {}
    lang_count: dict[str, int] = {}
    feedback_count: dict[str, int] = {}
    for r in recs:
        dept_count[r.department] = dept_count.get(r.department, 0) + 1
        feedback_count[r.feedback_status] = feedback_count.get(r.feedback_status, 0) + 1
        for lng in r.languages:
            lang_count[lng["name"]] = lang_count.get(lng["name"], 0) + 1
    return {
        "total": len(recs),
        "by_department": dict(sorted(dept_count.items(), key=lambda x: -x[1])),
        "by_language": dict(sorted(lang_count.items(), key=lambda x: -x[1])),
        "by_feedback": dict(sorted(feedback_count.items(), key=lambda x: -x[1])),
    }


def summarize_feedback() -> dict:
    recs = list_records()
    total = len(recs)
    rows: list[dict] = []
    positive = {"通过", "录用"}
    negative = {"淘汰", "面试后不符"}
    neutral = {"存疑"}

    feedback_total = 0
    pos_count = 0
    neg_count = 0
    neutral_count = 0

    for rec in recs:
        status = rec.feedback_status or "未反馈"
        if status != "未反馈":
            feedback_total += 1
        if status in positive:
            pos_count += 1
        elif status in negative:
            neg_count += 1
        elif status in neutral:
            neutral_count += 1

        rows.append({
            "ID": rec.id,
            "姓名": rec.display_name,
            "部门": rec.department,
            "反馈状态": status,
            "反馈说明": rec.feedback_note,
            "反馈时间": rec.feedback_updated_at,
            "来源文件": rec.source_file,
        })

    coverage = round(feedback_total / total * 100, 1) if total else 0.0
    positive_rate = round(pos_count / feedback_total * 100, 1) if feedback_total else 0.0
    negative_rate = round(neg_count / feedback_total * 100, 1) if feedback_total else 0.0
    neutral_rate = round(neutral_count / feedback_total * 100, 1) if feedback_total else 0.0

    return {
        "total_candidates": total,
        "feedback_total": feedback_total,
        "feedback_coverage": coverage,
        "positive_count": pos_count,
        "negative_count": neg_count,
        "neutral_count": neutral_count,
        "positive_rate": positive_rate,
        "negative_rate": negative_rate,
        "neutral_rate": neutral_rate,
        "status_distribution": stats().get("by_feedback", {}),
        "records": rows,
    }
