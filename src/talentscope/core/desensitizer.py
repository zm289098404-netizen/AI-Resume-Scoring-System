"""
PII 脱敏引擎
============
在文本送入 LLM 之前，用正则把姓名/电话/邮箱/身份证/地址等敏感信息替换为占位符。
脱敏映射表保存在内存中，输出报告时可还原。

设计原则：
- 仅做正则脱敏，简单高效（生产环境建议接 Presidio + 中文 NER）
- 映射表 per-session，绝不持久化
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field


# 中文姓名（2-4 字）— 简易规则，仅匹配「姓名：xxx」「Name: xxx」等明显场景
NAME_LABEL = re.compile(r"((?:姓名|名字|Name|name)[\s::]\s*)([\u4e00-\u9fa5A-Za-z]{2,10})")

# 手机号
PHONE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")

# 固话
TEL = re.compile(r"(?<!\d)(0\d{2,3}[- ]?\d{7,8})(?!\d)")

# 邮箱
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# 身份证（18 位）
ID_CARD = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")

# 详细地址（包含「省/市/区/路/号」等关键字）
ADDRESS = re.compile(
    r"[\u4e00-\u9fa5]{2,8}(?:省|市|自治区)[\u4e00-\u9fa5]{2,15}?"
    r"(?:区|县|市)[\u4e00-\u9fa5A-Za-z0-9]{2,30}?(?:路|街|号|大厦|小区|栋|室)"
)

# 生日（YYYY-MM-DD / YYYY年MM月DD日）
BIRTHDAY = re.compile(r"(?:19|20)\d{2}[-/年](?:0?[1-9]|1[0-2])[-/月](?:0?[1-9]|[12]\d|3[01])日?")

# ── 公平性保护属性 ──────────────────────────────────────────────────────────

# 性别（明确标签场景：「性别: 男」「Gender: Female」）
GENDER_LABEL = re.compile(
    r"((?:性别|Gender|gender)[\s::：]\s*)(男|女|Male|Female|male|female|先生|女士|Mr\.|Ms\.|Mrs\.)"
)
# 行文中的性别代词（他/她/他的/她的/Mr/Ms 等）
GENDER_PRONOUN = re.compile(
    r"\b(他|她|他的|她的|先生|女士|Mr\.|Ms\.|Mrs\.|Mr |Ms |Mrs )(?=[\u4e00-\u9fa5A-Za-z])"
)

# 年龄（「年龄: 28岁」「28 years old」「Age: 28」）
AGE_LABEL = re.compile(
    r"((?:年龄|Age|age)[\s::：]\s*)(\d{1,2}\s*(?:岁|years?\s*old|y\.?o\.?))"
)
# 出生年份（「出生于 1990」「Born in 1992」）
BIRTH_YEAR = re.compile(
    r"((?:出生于|出生年份|Born in|birth year)[\s::：]?\s*)((?:19|20)\d{2})"
)

# 籍贯/民族（「籍贯: 湖南」「民族: 汉族」）
NATIVE_PLACE = re.compile(
    r"((?:籍贯|民族|Ethnicity|ethnicity|Nationality|nationality|Origin)[\s::：]\s*)([\u4e00-\u9fa5A-Za-z]{2,10})"
)

# 政治面貌（「政治面貌: 党员」）
POLITICAL = re.compile(
    r"((?:政治面貌|党派|Political)[\s::：]\s*)([\u4e00-\u9fa5A-Za-z]{2,10})"
)

# 婚姻状况（「婚姻状况: 已婚」）
MARITAL = re.compile(
    r"((?:婚姻状况|婚否|Marital)[\s::：]\s*)([\u4e00-\u9fa5A-Za-z]{2,6})"
)


@dataclass
class Desensitizer:
    enabled: bool = True
    fields: list[str] = field(default_factory=lambda: ["name", "phone", "email", "id_card", "address", "gender", "age", "native_place"])
    _map: dict[str, str] = field(default_factory=dict)  # placeholder -> original
    _reverse: dict[str, str] = field(default_factory=dict)  # original -> placeholder

    def _gen(self, tag: str) -> str:
        token = f"[{tag}_{uuid.uuid4().hex[:6].upper()}]"
        return token

    def _replace(self, original: str, tag: str) -> str:
        if original in self._reverse:
            return self._reverse[original]
        ph = self._gen(tag)
        self._map[ph] = original
        self._reverse[original] = ph
        return ph

    def mask(self, text: str) -> str:
        """对外接口：返回脱敏后的文本"""
        if not self.enabled or not text:
            return text

        if "name" in self.fields:
            text = NAME_LABEL.sub(lambda m: m.group(1) + self._replace(m.group(2), "NAME"), text)
        if "phone" in self.fields:
            text = PHONE.sub(lambda m: self._replace(m.group(1), "PHONE"), text)
            text = TEL.sub(lambda m: self._replace(m.group(1), "TEL"), text)
        if "email" in self.fields:
            text = EMAIL.sub(lambda m: self._replace(m.group(0), "EMAIL"), text)
        if "id_card" in self.fields:
            text = ID_CARD.sub(lambda m: self._replace(m.group(1), "IDCARD"), text)
        if "address" in self.fields:
            text = ADDRESS.sub(lambda m: self._replace(m.group(0), "ADDR"), text)
        if "birthday" in self.fields:
            text = BIRTHDAY.sub(lambda m: self._replace(m.group(0), "BDAY"), text)
        # ── 公平性保护属性脱敏 ────────────────────────────────────────────────
        if "gender" in self.fields:
            text = GENDER_LABEL.sub(lambda m: m.group(1) + self._replace(m.group(2), "GENDER"), text)
            text = GENDER_PRONOUN.sub(lambda m: self._replace(m.group(1), "PRONOUN"), text)
        if "age" in self.fields:
            text = AGE_LABEL.sub(lambda m: m.group(1) + self._replace(m.group(2), "AGE"), text)
            text = BIRTH_YEAR.sub(lambda m: m.group(1) + self._replace(m.group(2), "BIRTHYR"), text)
        if "native_place" in self.fields:
            text = NATIVE_PLACE.sub(lambda m: m.group(1) + self._replace(m.group(2), "ORIGIN"), text)
            text = POLITICAL.sub(lambda m: m.group(1) + self._replace(m.group(2), "POLITICAL"), text)
            text = MARITAL.sub(lambda m: m.group(1) + self._replace(m.group(2), "MARITAL"), text)
        return text

    def restore(self, text: str) -> str:
        """把占位符替换回原始内容（仅用于本地输出展示）"""
        if not text:
            return text
        for ph, original in self._map.items():
            text = text.replace(ph, original)
        return text

    @property
    def map_size(self) -> int:
        return len(self._map)

    def export_map(self) -> dict[str, str]:
        """导出映射表副本（用于审计，谨慎使用）"""
        return dict(self._map)
