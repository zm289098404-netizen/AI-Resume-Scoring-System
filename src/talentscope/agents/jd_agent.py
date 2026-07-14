"""
JD 解析 Agent
=============
输入岗位描述，输出结构化：title / hard_skills / soft_skills / experience_years / education
"""
from __future__ import annotations

from talentscope.core.llm_client import get_llm_client

SYSTEM_PROMPT = """你是一名资深 HR/招聘顾问 (JD 解析 Agent)。
任务：把用户给的岗位描述（JD）拆解为结构化数据，便于后续与简历做匹配。

返回 JSON，schema：
{
  "title": "岗位名称",
  "hard_skills": [{"name": "技能名", "required": true/false, "weight": 0.5}],
  "soft_skills": ["软技能1", "软技能2"],
  "experience_years": 3,
  "education": "本科及以上",
  "responsibilities": ["职责1", "职责2", "职责3"]
}

要求：
- hard_skills 中 required=true 表示"必须有"，false 表示"加分项"
- weight 0~1，反映重要程度
- 严格只输出 JSON，无 markdown，无解释
"""


def parse_jd(jd_text: str) -> dict:
    client = get_llm_client()
    result = client.chat_json(SYSTEM_PROMPT, jd_text)
    # 兜底校验
    result.setdefault("title", "未命名岗位")
    result.setdefault("hard_skills", [])
    result.setdefault("soft_skills", [])
    result.setdefault("experience_years", 0)
    result.setdefault("education", "不限")
    return result
