"""
简历解析 Agent
==============
输入：脱敏后的简历文本
输出：结构化简历（技能/年限/学历/亮点/风险）
"""
from __future__ import annotations

from talentscope.core.llm_client import get_llm_client

SYSTEM_PROMPT = """你是一名经验丰富的招聘官 (简历解析 Agent)。
任务：把脱敏后的简历文本提取为结构化数据。

返回 JSON，schema：
{
  "candidate_id": "占位符 ID（如 R-XXXX）",
  "skills": ["技能1", "技能2"],
  "experience_years": 5,
  "education": "本科 / 硕士 / 博士",
  "highlights": ["亮点1", "亮点2"],
  "risks": ["风险点（如：跳槽频繁/技能不匹配/经验缺口）"]
}

要求：
- 简历中 PII 已经被遮罩为 [NAME_xxx] [PHONE_xxx] 等，请勿尝试还原
- skills 必须是标准技能名（如 Python、React、Kubernetes）
- 严格只输出 JSON
"""


def parse_resume(resume_text: str) -> dict:
    client = get_llm_client()
    result = client.chat_json(SYSTEM_PROMPT, resume_text)
    result.setdefault("candidate_id", "R-UNKNOWN")
    result.setdefault("skills", [])
    result.setdefault("experience_years", 0)
    result.setdefault("education", "未知")
    result.setdefault("highlights", [])
    result.setdefault("risks", [])
    return result
