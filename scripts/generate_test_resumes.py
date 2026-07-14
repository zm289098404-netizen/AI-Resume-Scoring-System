"""
生成 10 份合成 PDF 简历用于 TalentScope 测试
==============================================
- 全部虚构数据：姓名/电话/邮箱均为明显假数据（不侵犯任何真实人物隐私）
- 覆盖 10 种岗位画像 × 多语言能力 × 多部门归属
- 中文使用 Windows 自带 msyh.ttc（微软雅黑）
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.lib import colors

# ---------- 注册中文字体 ----------
FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
pdfmetrics.registerFont(TTFont("MSYH", FONT_PATH))

# ---------- 输出目录 ----------
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "samples" / "sample_resumes_pdf"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- 样式 ----------
styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="MSYH",
                    fontSize=18, leading=22, textColor=colors.HexColor("#1565c0"))
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="MSYH",
                    fontSize=13, leading=18, textColor=colors.HexColor("#1565c0"),
                    spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontName="MSYH",
                      fontSize=10.5, leading=16)
SMALL = ParagraphStyle("SMALL", parent=styles["BodyText"], fontName="MSYH",
                       fontSize=9.5, leading=14, textColor=colors.gray)


def build_resume(filename: str, candidate: dict) -> Path:
    out_path = OUT_DIR / filename
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=18*mm, bottomMargin=18*mm,
    )
    story = []

    # 标题：姓名 + 岗位
    story.append(Paragraph(f"{candidate['name']} · {candidate['target_role']}", H1))
    story.append(Paragraph(
        f"📞 {candidate['phone']} ｜ ✉️ {candidate['email']} ｜ 📍 {candidate['city']}"
        f" ｜ 出生年份：{candidate['birth_year']}",
        SMALL,
    ))
    story.append(Spacer(1, 6))

    # 基本信息表
    info = [
        ["最高学历", candidate["education"]],
        ["工作年限", f"{candidate['years']} 年"],
        ["期望薪资", candidate["salary"]],
        ["意向城市", candidate["city"]],
        ["求职状态", "在职 / 考虑机会"],
    ]
    t = Table(info, colWidths=[30*mm, 130*mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "MSYH"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f7fa")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dcdfe6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    # 技能
    story.append(Paragraph("一、专业技能", H2))
    story.append(Paragraph(candidate["skills"], BODY))

    # 语言
    story.append(Paragraph("二、语言能力", H2))
    story.append(Paragraph(candidate["languages"], BODY))

    # 工作经历
    story.append(Paragraph("三、工作经历", H2))
    for exp in candidate["experiences"]:
        story.append(Paragraph(
            f"<b>{exp['period']} ｜ {exp['company']} ｜ {exp['role']}</b>", BODY,
        ))
        for line in exp["bullets"]:
            story.append(Paragraph(f"• {line}", BODY))
        story.append(Spacer(1, 4))

    # 项目
    story.append(Paragraph("四、代表项目", H2))
    for proj in candidate["projects"]:
        story.append(Paragraph(f"<b>{proj['name']}</b>（{proj['stack']}）", BODY))
        story.append(Paragraph(proj["desc"], BODY))
        story.append(Spacer(1, 4))

    # 教育
    story.append(Paragraph("五、教育背景", H2))
    story.append(Paragraph(candidate["edu_detail"], BODY))

    # 自我评价
    story.append(Paragraph("六、自我评价", H2))
    story.append(Paragraph(candidate["summary"], BODY))

    doc.build(story)
    return out_path


# ============ 10 份虚构候选人 ============
CANDIDATES = [
    {
        "name": "张测试一", "phone": "138-0000-0001", "email": "test1@example.com",
        "city": "北京", "birth_year": 1990, "education": "本科",
        "target_role": "资深 Python 后端工程师", "years": 8,
        "salary": "30K-45K",
        "skills": "Python 3.10+、FastAPI、Django、Flask、Celery、Redis、PostgreSQL、MySQL、"
                  "Docker、Kubernetes、gRPC、RabbitMQ、单元测试、CI/CD（GitHub Actions）、性能调优。",
        "languages": "英语 流利（CET-6 580 分，可独立撰写英文技术文档，参与跨国会议）。",
        "experiences": [
            {"period": "2021.03 - 至今", "company": "某互联网公司", "role": "后端技术专家",
             "bullets": [
                 "主导用户中心微服务重构，QPS 从 2k 提升至 12k，P99 延迟下降 65%。",
                 "落地 FastAPI + asyncpg 异步栈，团队 8 人技术栈统一。",
                 "推动 GitHub Actions CI/CD，发布频率从周级提升到日级。",
             ]},
            {"period": "2018.07 - 2021.02", "company": "某电商平台", "role": "Python 高级工程师",
             "bullets": [
                 "负责订单服务，日订单峰值 500 万，构建幂等与最终一致性方案。",
                 "实现基于 Redis 的分布式锁与限流，故障率下降 80%。",
             ]},
        ],
        "projects": [
            {"name": "高并发用户中心", "stack": "FastAPI + PostgreSQL + Redis + K8s",
             "desc": "为千万级用户提供注册/登录/Token 服务，支持多机房部署。"},
            {"name": "实时风控网关", "stack": "Python + Kafka + ClickHouse",
             "desc": "毫秒级风险事件流处理，日处理事件 30 亿。"},
        ],
        "edu_detail": "2010.09 - 2014.06　某 985 大学　计算机科学与技术　学士",
        "summary": "8 年后端经验，熟悉高并发系统设计，沟通能力强，能带 5 人小团队。",
    },
    {
        "name": "李测试二", "phone": "138-0000-0002", "email": "test2@example.com",
        "city": "上海", "birth_year": 1992, "education": "硕士",
        "target_role": "LLM 算法工程师", "years": 6,
        "salary": "40K-60K",
        "skills": "PyTorch、Transformers、LangChain、LlamaIndex、RAG、向量检索（FAISS/Milvus）、"
                  "Prompt 工程、LoRA/QLoRA 微调、vLLM、模型评测、强化学习人类反馈（RLHF 基础）。",
        "languages": "英语 流利（CET-6、托福 95，能阅读发表英文论文）；日语 日常（JLPT N2）。",
        "experiences": [
            {"period": "2022.04 - 至今", "company": "某 AI 创新中心", "role": "LLM 算法工程师",
             "bullets": [
                 "搭建企业级 RAG 平台，接入 12 个业务方，问答准确率 87%。",
                 "完成 7B/13B 模型 QLoRA 微调，A/B 测试胜出率 +18%。",
                 "落地 vLLM 推理优化，吞吐提升 4x，单卡成本下降 60%。",
             ]},
            {"period": "2019.07 - 2022.03", "company": "某搜索公司", "role": "NLP 算法工程师",
             "bullets": [
                 "意图识别 + 实体抽取，覆盖 200+ 业务场景。",
                 "BERT 预训练与蒸馏，线上模型缩小到原来的 1/8。",
             ]},
        ],
        "projects": [
            {"name": "企业知识助手", "stack": "LangChain + Qwen + Milvus",
             "desc": "面向 5000 员工的内部知识问答，命中率 87%、首响 1.2s。"},
            {"name": "对话式 BI", "stack": "GPT-4 + Text-to-SQL",
             "desc": "自然语言转 SQL，准确率 91%，已替代 80% 的数据看板需求。"},
        ],
        "edu_detail": "2017.09 - 2019.06　某 211 大学　计算机科学　硕士\n"
                      "2013.09 - 2017.06　某 211 大学　数学与应用数学　学士",
        "summary": "聚焦 LLM 落地，从训练、推理到产品化均有完整经验，关注 ROI 与上线效果。",
    },
    {
        "name": "王测试三", "phone": "138-0000-0003", "email": "test3@example.com",
        "city": "杭州", "birth_year": 1991, "education": "硕士",
        "target_role": "高级数据科学家", "years": 7,
        "salary": "35K-50K",
        "skills": "Python（pandas/numpy/scikit-learn）、SQL（Hive/Spark SQL）、特征工程、"
                  "XGBoost、LightGBM、时间序列（Prophet）、A/B 实验、因果推断、Tableau。",
        "languages": "英语 日常（CET-4 540 分），可读英文论文与文档。",
        "experiences": [
            {"period": "2020.06 - 至今", "company": "某出行公司", "role": "数据科学家",
             "bullets": [
                 "用户分层 + 营销策略建模，ROI 提升 23%。",
                 "搭建用户 LTV 预测模型，MAE 下降 18%，指导预算分配。",
             ]},
            {"period": "2017.07 - 2020.05", "company": "某金融科技公司", "role": "数据分析师",
             "bullets": [
                 "授信风险模型 KS 0.42，坏账率下降 15%。",
                 "搭建实时报表体系，覆盖 30+ 业务模块。",
             ]},
        ],
        "projects": [
            {"name": "用户 LTV 预测", "stack": "LightGBM + Spark",
             "desc": "为亿级用户预测 90 天价值，AUC 0.83。"},
            {"name": "营销 A/B 平台", "stack": "Python + ClickHouse",
             "desc": "支持 50+ 业务方并发实验，统计显著性自动判定。"},
        ],
        "edu_detail": "2015.09 - 2017.06　某 985 大学　应用统计　硕士",
        "summary": "数据驱动业务增长经验丰富，擅长把模型转化为可执行运营策略。",
    },
    {
        "name": "赵测试四", "phone": "138-0000-0004", "email": "test4@example.com",
        "city": "深圳", "birth_year": 1988, "education": "本科",
        "target_role": "Azure 云架构师", "years": 10,
        "salary": "45K-70K",
        "skills": "Azure（AKS、App Service、Functions、Service Bus、Cosmos DB、Key Vault、APIM）、"
                  "Terraform、Bicep、Kubernetes、Helm、Istio、Prometheus、Grafana、"
                  "成本治理（FinOps）、混合云架构、Well-Architected Framework。",
        "languages": "英语 流利（雅思 7.0，国际客户口语沟通无障碍）；德语 日常（A2，曾驻德 6 个月）。",
        "experiences": [
            {"period": "2019.05 - 至今", "company": "某外资云服务商", "role": "首席云架构师",
             "bullets": [
                 "主导 30+ 企业客户 Azure 迁移，整体云成本下降 28%。",
                 "设计多区域容灾架构，RTO < 15 分钟。",
                 "推动团队全部 IaC 化（Terraform），变更失败率下降 70%。",
             ]},
            {"period": "2014.06 - 2019.04", "company": "某互联网公司", "role": "高级运维工程师",
             "bullets": [
                 "K8s 集群规模 1500+ Pod，可用性 99.99%。",
             ]},
        ],
        "projects": [
            {"name": "跨国零售云迁移", "stack": "Azure + Terraform + AKS",
             "desc": "30+ 业务系统平滑上云，停机 < 4 小时。"},
            {"name": "FinOps 治理平台", "stack": "Azure Cost Mgmt + Power BI",
             "desc": "可视化成本，3 个月节省云开销 230 万元。"},
        ],
        "edu_detail": "2008.09 - 2012.06　某 211 大学　信息工程　学士",
        "summary": "10 年云与基础架构经验，熟悉大型企业治理流程，能直接对接客户 CTO。",
    },
    {
        "name": "孙测试五", "phone": "138-0000-0005", "email": "test5@example.com",
        "city": "广州", "birth_year": 1995, "education": "本科",
        "target_role": "高级前端工程师", "years": 5,
        "salary": "25K-35K",
        "skills": "React 18、Next.js、TypeScript、Vue 3、Vite、Webpack、Tailwind、"
                  "微前端（qiankun）、性能优化、可访问性 a11y、Jest/Playwright。",
        "languages": "英语 日常（CET-4 520 分），能读英文技术文档。",
        "experiences": [
            {"period": "2022.03 - 至今", "company": "某互联网 BU", "role": "高级前端",
             "bullets": [
                 "重构后台中台，首屏加载从 4.8s 降至 1.2s。",
                 "搭建组件库 + Storybook，跨 6 个业务复用。",
             ]},
            {"period": "2020.07 - 2022.02", "company": "某 SaaS 公司", "role": "前端工程师",
             "bullets": ["主导 Vue 2 → Vue 3 升级，性能提升 35%。"]},
        ],
        "projects": [
            {"name": "可视化拖拽搭建", "stack": "React + DnD + JSON Schema",
             "desc": "低代码搭建后台页面，业务自助率 70%。"},
        ],
        "edu_detail": "2016.09 - 2020.06　某双非本科　软件工程　学士",
        "summary": "热爱前端工程化，关注用户体验和性能指标。",
    },
    {
        "name": "周测试六", "phone": "138-0000-0006", "email": "test6@example.com",
        "city": "上海", "birth_year": 1989, "education": "本科",
        "target_role": "Java 高级工程师（金融）", "years": 9,
        "salary": "30K-45K",
        "skills": "Java 17、Spring Boot 3、Spring Cloud、Dubbo、MyBatis、ShardingSphere、"
                  "Kafka、RocketMQ、MySQL 调优、Redis、JVM 调优、DDD、领域建模。",
        "languages": "英语 日常（CET-4），能读英文文档。",
        "experiences": [
            {"period": "2018.04 - 至今", "company": "某金融 BU", "role": "Java 技术专家",
             "bullets": [
                 "核心交易链路改造，TPS 从 800 提升到 5000。",
                 "推动单元化部署，多机房切流秒级完成。",
             ]},
            {"period": "2015.07 - 2018.03", "company": "某第三方支付", "role": "高级开发",
             "bullets": ["对账系统重构，日终对账时间从 2 小时降至 12 分钟。"]},
        ],
        "projects": [
            {"name": "交易核心系统", "stack": "Spring Boot + ShardingSphere + RocketMQ",
             "desc": "支持日均 8000 万笔交易，可用性 99.995%。"},
        ],
        "edu_detail": "2011.09 - 2015.06　某 211 大学　软件工程　学士",
        "summary": "金融领域 9 年 Java 经验，重视稳定性与可观测性。",
    },
    {
        "name": "吴测试七", "phone": "138-0000-0007", "email": "test7@example.com",
        "city": "北京", "birth_year": 1990, "education": "本科",
        "target_role": "DevOps / SRE 工程师", "years": 8,
        "salary": "35K-50K",
        "skills": "Kubernetes、Helm、ArgoCD、GitOps、Terraform、Ansible、Prometheus、"
                  "Grafana、Loki、ELK、Istio、混沌工程（Chaos Mesh）、Python/Go 脚本。",
        "languages": "英语 流利（CET-6 600 分，独立处理国际开源社区 issue）。",
        "experiences": [
            {"period": "2019.03 - 至今", "company": "某技术研发部", "role": "SRE Tech Lead",
             "bullets": [
                 "构建多集群 GitOps 平台，发布数从月 50 → 日 200+。",
                 "P1 故障 MTTR 从 45 分钟降至 8 分钟。",
             ]},
            {"period": "2016.06 - 2019.02", "company": "某互联网公司", "role": "运维工程师",
             "bullets": ["大规模 K8s 集群运维，节点 800+。"]},
        ],
        "projects": [
            {"name": "GitOps 发布平台", "stack": "ArgoCD + Helm + Prometheus",
             "desc": "统一 12 BU 发布流程，灰度全自动。"},
        ],
        "edu_detail": "2008.09 - 2012.06　某 211 大学　计算机　学士",
        "summary": "8 年 SRE 经验，关注稳定性、可观测性与团队效率。",
    },
    {
        "name": "郑测试八", "phone": "138-0000-0008", "email": "test8@example.com",
        "city": "深圳", "birth_year": 1993, "education": "本科",
        "target_role": "iOS 高级工程师", "years": 6,
        "salary": "28K-40K",
        "skills": "Swift 5、SwiftUI、UIKit、Combine、RxSwift、Objective-C、性能调优、"
                  "组件化、Flutter 入门、CI（Fastlane）。",
        "languages": "英语 日常（CET-4），可读 Apple 官方英文文档；韩语 入门（TOPIK 2 级）。",
        "experiences": [
            {"period": "2021.04 - 至今", "company": "某互联网 BU", "role": "iOS 高级工程师",
             "bullets": [
                 "主导 App SwiftUI 重写，包体下降 22%，启动速度 +35%。",
                 "组件化拆分 30+ 模块，编译时间减半。",
             ]},
            {"period": "2018.07 - 2021.03", "company": "某社交 App", "role": "iOS 工程师",
             "bullets": ["IM 模块重构，弱网消息送达率 +12%。"]},
        ],
        "projects": [
            {"name": "短视频客户端", "stack": "Swift + AVFoundation",
             "desc": "支持千万 DAU，首帧渲染 < 300ms。"},
        ],
        "edu_detail": "2014.09 - 2018.06　某双非本科　计算机　学士",
        "summary": "6 年 iOS 经验，关注体验细节与工程化。",
    },
    {
        "name": "钱测试九", "phone": "138-0000-0009", "email": "test9@example.com",
        "city": "新加坡（可回国）", "birth_year": 1987, "education": "硕士",
        "target_role": "海外交付项目总监", "years": 12,
        "salary": "50K-80K",
        "skills": "PMP、敏捷（SAFe）、跨文化团队管理、合同与商务谈判、风险管理、"
                  "Jira/Confluence、汇报与客户管理（C-Level）、东南亚/欧洲交付经验。",
        "languages": "英语 母语水平（在美工作 5 年，雅思 8.5）；"
                     "法语 流利（DELF B2，曾驻法 2 年）；"
                     "西班牙语 日常（DELE A2，可日常对话）。",
        "experiences": [
            {"period": "2020.01 - 至今", "company": "某海外交付中心", "role": "高级交付总监",
             "bullets": [
                 "管理 5 个跨国项目，合同总额 1.2 亿，按期交付率 96%。",
                 "建立跨时区作战室，欧美团队协同效率 +30%。",
             ]},
            {"period": "2014.07 - 2019.12", "company": "某全球咨询公司", "role": "项目经理",
             "bullets": ["欧洲银行核心系统升级，2 年内零重大事故。"]},
        ],
        "projects": [
            {"name": "东南亚电信 BSS 升级", "stack": "Microservices + AWS",
             "desc": "覆盖 4 个国家，5000 万用户平滑迁移。"},
        ],
        "edu_detail": "2010.09 - 2013.06　某海外名校　工商管理　MBA",
        "summary": "12 年跨国交付经验，擅长多元文化团队与高复杂度客户管理。",
    },
    {
        "name": "冯测试十", "phone": "138-0000-0010", "email": "test10@example.com",
        "city": "北京", "birth_year": 1989, "education": "本科",
        "target_role": "高级安全工程师（政企）", "years": 9,
        "salary": "35K-50K",
        "skills": "渗透测试、代码审计、SAST/DAST、OWASP Top 10、等保 2.0、"
                  "ATT&CK、SIEM（Splunk）、SOAR、零信任、Python 安全脚本、应急响应。",
        "languages": "英语 流利（CET-6 595，能阅读英文 CVE 公告与厂商安全白皮书）；"
                     "俄语 日常（俄语专业四级），可处理俄语客户基础沟通。",
        "experiences": [
            {"period": "2019.06 - 至今", "company": "某政企 BU", "role": "安全负责人",
             "bullets": [
                 "牵头 20+ 政企客户等保 2.0 三级认证，全部一次通过。",
                 "建立漏洞响应 SOP，平均处置时长 < 4 小时。",
             ]},
            {"period": "2015.07 - 2019.05", "company": "某网络安全公司", "role": "渗透测试工程师",
             "bullets": ["完成 100+ 次甲方渗透项目，挖掘高危漏洞 200+ 个。"]},
        ],
        "projects": [
            {"name": "金融行业红蓝对抗", "stack": "Cobalt Strike + ATT&CK",
             "desc": "为大型银行实施 3 周红蓝演练，发现关键路径 5 条。"},
        ],
        "edu_detail": "2008.09 - 2012.06　某 211 大学　信息安全　学士",
        "summary": "9 年攻防与合规双线经验，擅长政企客户安全建设全周期。",
    },
]


def main():
    print(f"输出目录：{OUT_DIR}")
    for i, c in enumerate(CANDIDATES, 1):
        fname = f"resume_{i:02d}_{c['name']}.pdf"
        p = build_resume(fname, c)
        print(f"  ✅ [{i:02d}] {p.name}  ({p.stat().st_size // 1024} KB)")
    print(f"\n共生成 {len(CANDIDATES)} 份 PDF 简历。")


if __name__ == "__main__":
    main()
