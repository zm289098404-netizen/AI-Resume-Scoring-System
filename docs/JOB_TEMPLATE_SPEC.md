# 岗位模板库规范（严谨版）

## 目的

岗位模板库用于沉淀关键岗位的统一标准，避免不同招聘人员对岗位要求理解不一致。

## 模板字段规范

每个模板必须包含以下字段：

- id: 模板唯一标识，不可重复
- version: 模板版本号，建议使用 YYYY.MM
- name: 岗位名称
- role_family: 岗位族群（研发/测试/运维/数据等）
- criticality_level: 关键级别（高/中高/中）
- business_context: 岗位业务背景
- experience_years: 最低经验要求（整数）
- education: 学历要求
- must_have_skills: 必备技能列表
- required_languages: 语言要求列表（name/min_level/business_impact）
- responsibilities: 职责列表
- hard_requirements: 硬性要求列表（requirement/rationale/evidence_hint）
- preferred_requirements: 加分项列表
- risk_controls: 风险控制点列表
- interview_focus: 面试关注点列表
- jd_text: 可直接应用到系统的标准JD文本

## 质量门槛

1. 每个硬性要求必须提供业务理由和核验证据提示。
2. 必备技能必须可映射到可验证的项目经验。
3. 风险控制点必须覆盖“贡献真实性”和“交付稳定性”两类风险。
4. 模板更新必须附版本变更说明。

## 更新流程

1. 由 HR 与用人经理共同提出模板变更。
2. 技术支持更新 config/job_templates.json。
3. 进行样本岗位回归验证后再发布。
4. 在周复盘中观察模板对应岗位的反馈覆盖率和正向反馈率。
