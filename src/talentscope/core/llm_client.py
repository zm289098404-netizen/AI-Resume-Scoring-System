"""
LLM 客户端
==========
统一封装：
- AzureOpenAIClient：调用 Azure OpenAI
- OpenAICompatibleClient：调用所有 OpenAI 兼容端点
  （DeepSeek / 通义千问 / 智谱 GLM / Moonshot Kimi / 文心一言 等国内主流模型）
- MockClient：本地规则模拟，无需 API Key

通过 config.json 中 llm.provider 切换（兼容旧 llm.mode 字段）。
"""
from __future__ import annotations

import json
import random
import re
from typing import Any

from talentscope.config_loader import get_config, get_provider


# ---------------- 真实 Azure 客户端 ----------------
class AzureOpenAIClient:
    def __init__(self, cfg: dict):
        from openai import AzureOpenAI
        self._client = AzureOpenAI(
            azure_endpoint=cfg["azure_endpoint"],
            api_key=cfg["azure_api_key"],
            api_version=cfg["azure_api_version"],
        )
        self._deployment = cfg["azure_deployment"]
        self._temperature = cfg.get("temperature", 0.2)
        self._max_tokens = cfg.get("max_tokens", 2000)

    def chat_json(self, system: str, user: str) -> dict:
        """要求 LLM 返回 JSON 格式的内容"""
        resp = self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": system + "\n\n严格只返回 JSON，不要解释，不要 markdown 代码块。"},
                {"role": "user", "content": user},
            ],
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content or "{}"
        return _safe_json_loads(text)

    def chat_text(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()


# ---------------- OpenAI 兼容客户端（DeepSeek / Qwen / GLM / Kimi / ERNIE） ----------------
class OpenAICompatibleClient:
    """统一封装 OpenAI 兼容端点。"""

    def __init__(self, cfg: dict):
        from openai import OpenAI
        api_base = cfg.get("api_base", "").rstrip("/")
        if not api_base:
            raise ValueError("缺少 api_base，请在模型目录中配置或在 UI 中填写。")
        self._client = OpenAI(
            base_url=api_base,
            api_key=cfg.get("api_key", ""),
        )
        self._model = cfg.get("model") or cfg.get("default_model") or "gpt-3.5-turbo"
        self._temperature = float(cfg.get("temperature", 0.2))
        self._max_tokens = int(cfg.get("max_tokens", 2000))
        self._supports_json = bool(cfg.get("supports_json_mode", True))

    def chat_json(self, system: str, user: str) -> dict:
        kwargs: dict[str, Any] = dict(
            model=self._model,
            messages=[
                {"role": "system", "content": system + "\n\n严格只返回 JSON，不要解释，不要 markdown 代码块。"},
                {"role": "user", "content": user},
            ],
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        if self._supports_json:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            # 部分平台不支持 response_format，降级重试
            if "response_format" in kwargs:
                kwargs.pop("response_format", None)
                try:
                    resp = self._client.chat.completions.create(**kwargs)
                except Exception as e2:
                    return {"_error": f"{type(e2).__name__}: {e2}", "_raw": ""}
            else:
                return {"_error": f"{type(e).__name__}: {e}", "_raw": ""}
        text = resp.choices[0].message.content or "{}"
        return _safe_json_loads(text)

    def chat_text(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
class MockClient:
    """无 API Key 时使用的模拟客户端，基于关键字提取生成合理的结构化结果。"""

    def chat_json(self, system: str, user: str) -> dict:
        sys_lower = system.lower()
        if "jd" in sys_lower or "职位" in system or "岗位" in system:
            return self._mock_jd(user)
        if "简历" in system or "resume" in sys_lower:
            return self._mock_resume(user)
        if "匹配" in system or "match" in sys_lower:
            return self._mock_match(user)
        return {"raw": user[:200]}

    def chat_text(self, system: str, user: str) -> str:
        return f"[Mock LLM 文本输出]\n根据输入：{user[:80]}...\n推荐理由：候选人在关键技能上有较好覆盖，建议进一步面试。"

    # ---- 模拟方法 ----
    def _extract_skills(self, text: str) -> list[str]:
        """从原文里粗略提取技能词"""
        from talentscope.config_loader import get_skills_taxonomy
        taxonomy = get_skills_taxonomy()
        all_skills = []
        for cat in taxonomy["categories"].values():
            all_skills.extend(cat)
        # 同义词归一
        for syn, std in taxonomy.get("synonyms", {}).items():
            if syn.lower() in text.lower() and std not in text:
                text += " " + std
        found = []
        text_lower = text.lower()
        for s in all_skills:
            if s.lower() in text_lower:
                found.append(s)
        return list(dict.fromkeys(found))  # 去重保序

    def _mock_jd(self, jd_text: str) -> dict:
        skills = self._extract_skills(jd_text)
        years_match = re.search(r"(\d+)[\s\-到至~]*年", jd_text)
        years = int(years_match.group(1)) if years_match else 3
        return {
            "title": (jd_text.split("\n")[0][:30] or "未命名岗位"),
            "hard_skills": [{"name": s, "required": True, "weight": 1.0} for s in skills[:8]],
            "soft_skills": ["团队协作", "沟通能力"],
            "experience_years": years,
            "education": "本科及以上",
            "responsibilities": [
                "负责核心业务模块设计与开发",
                "参与跨团队协作与技术评审",
                "持续优化系统性能与稳定性",
            ],
        }

    def _mock_resume(self, resume_text: str) -> dict:
        skills = self._extract_skills(resume_text)
        years_match = re.search(r"(\d+)[\s\-到至~]*年", resume_text)
        years = int(years_match.group(1)) if years_match else random.randint(2, 8)
        # 学历
        edu = "本科"
        for e in ["博士", "硕士", "本科", "大专"]:
            if e in resume_text:
                edu = e
                break
        return {
            "candidate_id": f"R-{random.randint(1000, 9999)}",
            "skills": skills,
            "experience_years": years,
            "education": edu,
            "highlights": [
                "有完整项目交付经验",
                "熟悉云原生与 DevOps 流程",
            ][:2],
            "risks": [],
        }

    def _mock_match(self, payload: str) -> dict:
        """payload 是 JSON 字符串：包含 jd + resume"""
        try:
            data = json.loads(payload)
        except Exception:
            data = {}
        jd = data.get("jd", {})
        resume = data.get("resume", {})

        jd_skills = {s["name"].lower() for s in jd.get("hard_skills", [])}
        resume_skills = {s.lower() for s in resume.get("skills", [])}
        hit = jd_skills & resume_skills
        miss = jd_skills - resume_skills

        skill_score = (len(hit) / max(len(jd_skills), 1)) * 100
        exp_score = min(resume.get("experience_years", 0) / max(jd.get("experience_years", 1), 1), 1.5) * 100
        exp_score = min(exp_score, 100)
        soft_score = 75 + random.randint(-10, 15)
        edu_score = 80 if resume.get("education") in ("本科", "硕士", "博士") else 60

        weights = get_config()["scoring"]["weights"]
        total = (
            skill_score * weights["hard_skill"]
            + exp_score * weights["experience"]
            + soft_score * weights["soft_skill"]
            + edu_score * weights["education"]
        )

        return {
            "total_score": round(total, 1),
            "dimensions": {
                "hard_skill": round(skill_score, 1),
                "experience": round(exp_score, 1),
                "soft_skill": round(soft_score, 1),
                "education": round(edu_score, 1),
            },
            "matched_skills": sorted(hit),
            "missing_skills": sorted(miss),
            "recommendation": _gen_recommendation(total, hit, miss),
            "risks": _gen_risks(resume),
        }


def _gen_recommendation(score: float, hit: set, miss: set) -> str:
    if score >= 85:
        return f"强烈推荐：覆盖关键技能 {len(hit)} 项，建议优先安排面试。"
    if score >= 70:
        return f"推荐：核心技能匹配良好，缺口 ({', '.join(list(miss)[:3])}) 可在入职后补齐。"
    if score >= 55:
        return f"备选：存在明显技能缺口 ({len(miss)} 项)，需在面试中重点考察。"
    return "不推荐：技能与岗位要求差距较大。"


def _gen_risks(resume: dict) -> list[str]:
    risks = []
    yrs = resume.get("experience_years", 0)
    if yrs < 2:
        risks.append("工作年限偏短，需评估独立交付能力")
    return risks


def _safe_json_loads(text: str) -> dict:
    """尝试解析 LLM 返回的 JSON，容错处理"""
    text = text.strip()
    # 去除可能的 markdown 包裹
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取第一个 {...}
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"_error": "LLM 返回非 JSON", "_raw": text[:500]}


# ---------------- 工厂 ----------------
_client_instance = None


def get_llm_client():
    """单例工厂。按 llm.provider 派发，兼容旧 llm.mode 字段。"""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    cfg = get_config()["llm"]

    # 兼容旧配置：mode == "mock"/"azure_openai" 映射到 provider
    provider_id = cfg.get("provider") or cfg.get("mode") or "mock"
    prov = get_provider(provider_id) or {}
    api_type = prov.get("api_type") or (
        "azure_openai" if provider_id == "azure_openai" else
        "mock" if provider_id == "mock" else "openai_compatible"
    )

    if api_type == "mock":
        _client_instance = MockClient()
        return _client_instance

    if api_type == "azure_openai":
        # 必须有 api_key、endpoint、deployment
        if not (cfg.get("azure_api_key") and cfg.get("azure_endpoint") and cfg.get("azure_deployment")):
            _client_instance = MockClient()
        else:
            _client_instance = AzureOpenAIClient(cfg)
        return _client_instance

    # openai_compatible：DeepSeek / Qwen / GLM / Kimi / ERNIE
    if not cfg.get("api_key"):
        _client_instance = MockClient()
        return _client_instance

    merged = dict(prov)              # api_base / supports_json_mode / default_model 等
    merged.update(cfg)               # 用户配置覆盖
    merged.setdefault("model", prov.get("default_model"))
    _client_instance = OpenAICompatibleClient(merged)
    return _client_instance


def reset_client():
    """配置变更后调用"""
    global _client_instance
    _client_instance = None
