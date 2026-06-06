"""
TalentScope Streamlit 控制台
============================
3 个 Tab：
  ① JD 匹配评分（支持「上传」或「从简历库选人」两种来源）
  ② 简历库管理（批量导入 / 按部门-语言筛选 / 编辑 / 删除）
  ③ 语言与部门管理（管理员 DIY，可扩展任意小语种 / 部门）
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import streamlit as st

from talentscope.config_loader import (
    get_config, get_root, get_skills_taxonomy,
    get_languages, save_languages,
    get_departments, save_departments,
    save_config, reload_config,
    get_models_catalog, get_provider,
)
from talentscope.core import resume_library as lib
from talentscope.core import llm_client
from talentscope.pipeline import ResumeInput, run as run_pipeline, run_from_library

FEEDBACK_OPTIONS = ["未反馈", "通过", "存疑", "淘汰", "录用", "面试后不符"]


def _fmt_lang(x, key="level"):
    if isinstance(x, dict):
        return f'{x.get("name", "?")}({x.get(key, "")})'
    return str(x)


def _status_label(score: float, threshold: int) -> str:
    if score >= threshold:
        return "🟢 推荐"
    if score >= threshold - 15:
        return "🟡 备选"
    return "🔴 不推荐"


def _render_result_details(candidates: list[dict], threshold: int) -> None:
    valid_candidates = [c for c in candidates if "error" not in c]
    if not valid_candidates:
        return

    st.markdown("### 🧾 评分证据与面试辅助")
    for idx, candidate in enumerate(
        sorted(valid_candidates, key=lambda item: item["match"]["total_score"], reverse=True)[:5],
        1,
    ):
        match = candidate["match"]
        resume = candidate["resume"]
        title = f"Top {idx} · {candidate['file']} · {match['total_score']} 分 · {_status_label(match['total_score'], threshold)}"
        with st.expander(title, expanded=(idx == 1)):
            c1, c2, c3 = st.columns([1.15, 1, 1])
            with c1:
                st.markdown("**评分证据**")
                for item in match.get("evidence_summary", []):
                    st.markdown(f"- {item}")
                evidence = match.get("evidence", {})
                if evidence:
                    st.caption(
                        f"置信度 {match.get('confidence', '—')} · 亮点证据 {len(evidence.get('highlight_evidence', []))} 条"
                    )
                if match.get("recommendation"):
                    st.info(match["recommendation"])
            with c2:
                st.markdown("**建议核验项**")
                for item in match.get("follow_up_checks", []):
                    st.markdown(f"- {item}")
                if match.get("risks"):
                    st.markdown("**风险提示**")
                    for item in match.get("risks", []):
                        st.markdown(f"- {item}")
            with c3:
                st.markdown("**建议追问**")
                for question in match.get("interview_questions", []):
                    st.markdown(f"- {question}")
                if resume.get("highlights"):
                    st.markdown("**简历亮点**")
                    for item in resume.get("highlights", [])[:3]:
                        st.markdown(f"- {item}")


def _render_governance_panel() -> None:
    st.markdown("### 🛡️ 评测与治理")
    g1, g2 = st.columns(2)
    with g1:
        st.markdown(
            """
            **决策原则**

            - 评分仅作为招聘辅助，不替代人工录用决策
            - 分数由本地规则稳定计算，便于复核与复现
            - 推荐理由、追问建议由模型生成，但必须结合证据核验
            - 优先关注岗位相关能力，不以非岗位因素做正向加分
            """
        )
    with g2:
        st.markdown(
            """
            **上线前检查**

            - 先用试点样本校准岗位模板和门槛分数
            - 对通过/淘汰结果保留人工反馈，形成评测集
            - 对缺失技能、语言和经验缺口做面试复核
            - 生产环境建议启用专属租户、网络隔离和日志审计
            """
        )


def _render_feedback_metrics() -> None:
    summary = lib.summarize_feedback()
    st.markdown("### 📈 试点评测概览")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("反馈覆盖率", f"{summary['feedback_coverage']}%")
    c2.metric("正向反馈率", f"{summary['positive_rate']}%")
    c3.metric("负向反馈率", f"{summary['negative_rate']}%")
    c4.metric("存疑占比", f"{summary['neutral_rate']}%")

    if summary["records"]:
        eval_df = pd.DataFrame(summary["records"])
        csv = eval_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 下载反馈评测 CSV",
            data=csv,
            file_name="feedback_evaluation.csv",
            mime="text/csv",
            width="stretch",
        )
    st.caption("说明：当前评测基于人才库中的人工反馈状态汇总，用于试点阶段观察正向/负向反馈分布与覆盖率。")


# ---------------- 页面配置 ----------------
st.set_page_config(
    page_title="TalentScope · AI 简历匹配评分",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- 主题 CSS（深色玻璃 + 渐变） ----------
st.markdown(
    """
    <style>
    /* 隐藏 Streamlit 顶部菜单与水印，让画面更干净 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: transparent;}

    /* 主容器底色 */
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px;}

    /* ===== Hero 头条 ===== */
    .ts-hero {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 45%, #f093fb 100%);
        padding: 28px 32px;
        border-radius: 18px;
        color: #fff;
        margin-bottom: 18px;
        box-shadow: 0 10px 30px rgba(102,126,234,.35);
        position: relative;
        overflow: hidden;
    }
    .ts-hero::before {
        content: ""; position: absolute; right: -60px; top: -60px;
        width: 220px; height: 220px; border-radius: 50%;
        background: rgba(255,255,255,.08);
    }
    .ts-hero::after {
        content: ""; position: absolute; right: 80px; bottom: -90px;
        width: 180px; height: 180px; border-radius: 50%;
        background: rgba(255,255,255,.06);
    }
    .ts-hero h1 {
        font-size: 34px; font-weight: 800; margin: 0 0 6px 0;
        letter-spacing: 1px; line-height: 1.1;
        text-shadow: 0 2px 8px rgba(0,0,0,.15);
    }
    .ts-hero p {
        font-size: 14px; margin: 0; opacity: .92;
    }
    .ts-hero .badges {margin-top: 12px;}
    .ts-hero .badge {
        display: inline-block; padding: 4px 12px; margin-right: 8px;
        background: rgba(255,255,255,.18); border-radius: 999px;
        font-size: 12px; backdrop-filter: blur(6px);
        border: 1px solid rgba(255,255,255,.28);
    }

    /* ===== 玻璃质感状态卡 ===== */
    .glass-card {
        background: linear-gradient(135deg, rgba(255,255,255,.85) 0%, rgba(245,247,250,.65) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,.6);
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 4px 14px rgba(17,17,26,.06);
        transition: transform .18s ease, box-shadow .18s ease;
        height: 100%;
    }
    .glass-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 22px rgba(17,17,26,.1);
    }
    .glass-card .label {
        font-size: 11px; font-weight: 600;
        color: #6b7280; text-transform: uppercase; letter-spacing: 1px;
        margin-bottom: 6px;
    }
    .glass-card .value {
        font-size: 18px; font-weight: 700;
        background: linear-gradient(90deg, #667eea, #764ba2);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .glass-card .sub {
        font-size: 12px; color: #9ca3af; margin-top: 4px;
    }

    /* ===== 模型选择卡片 ===== */
    .model-card {
        background: linear-gradient(135deg, #f8fafc, #ffffff);
        border: 1px solid #e5e7eb; border-radius: 12px;
        padding: 14px 16px; margin-bottom: 10px;
    }
    .model-card .head {
        font-size: 15px; font-weight: 700; color: #1e293b;
    }
    .model-card .tag {
        display: inline-block; font-size: 10px; padding: 2px 8px;
        border-radius: 6px; margin-left: 8px; vertical-align: middle;
    }
    .tag-cn  {background: #fee2e2; color: #b91c1c;}
    .tag-local {background: #dcfce7; color: #15803d;}
    .tag-intl {background: #dbeafe; color: #1d4ed8;}
    .tag-demo {background: #fef3c7; color: #92400e;}

    /* ===== Tab 美化 ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px; border-bottom: none;
    }
    .stTabs [data-baseweb="tab"] {
        background: #f1f5f9; border-radius: 10px 10px 0 0;
        padding: 10px 22px; font-weight: 600;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(102,126,234,.3);
    }

    /* ===== 按钮强化 ===== */
    .stButton > button, .stDownloadButton > button {
        border-radius: 10px; font-weight: 600;
        transition: all .18s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 14px rgba(102,126,234,.25);
    }
    .stForm button[kind="formSubmit"] {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white; border: none;
    }

    /* 输入控件圆角 */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div,
    .stNumberInput input {
        border-radius: 10px !important;
    }

    /* 分割线渐变 */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #cbd5e1, transparent);
        margin: 18px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Hero ----------
st.markdown(
    """
    <div class="ts-hero">
        <h1>🎯 TalentScope</h1>
        <p>AI 简历智能匹配评分系统 · 博彦科技 2026 AI 大奖参赛项目</p>
        <div class="badges">
            <span class="badge">🤖 多模型可切换</span>
            <span class="badge">🇨🇳 国产 5 大 + 🏠 本地部署</span>
            <span class="badge">🔒 PII 脱敏</span>
            <span class="badge">📊 5 维评分</span>
            <span class="badge">📄 一键报告</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------- 加载配置 ----------------
try:
    cfg = get_config()
    taxonomy = get_skills_taxonomy()
    lang_cfg = get_languages()
    dept_cfg = get_departments()
except Exception as e:
    st.error(f"配置加载失败：{e}")
    st.stop()

LANG_NAMES = [l["name"] for l in lang_cfg["languages"]]
LANG_LEVELS = lang_cfg.get("levels", ["入门", "日常", "流利", "母语"])
DEPT_NAMES = [d["name"] for d in dept_cfg["departments"]]

# ---------------- 顶部状态条（玻璃卡） ----------------
c1, c2, c3, c4 = st.columns(4)
_llm = cfg.get("llm", {})
_prov_id = _llm.get("provider") or _llm.get("mode") or "mock"
_prov_info = get_provider(_prov_id) or {}
_prov_name = f"{_prov_info.get('emoji','')} {_prov_info.get('name', _prov_id)}".strip()
_prov_group = _prov_info.get("group", "—")
_model_name = _llm.get("model") or _prov_info.get("default_model", "-")
stats0 = lib.stats()
d_on = "✅ 已启用" if cfg["desensitize"]["enabled"] else "⚠️ 已关闭"

with c1:
    st.markdown(
        f'<div class="glass-card"><div class="label">🤖 当前模型</div>'
        f'<div class="value">{_prov_name}</div>'
        f'<div class="sub">📦 {_model_name} · {_prov_group}</div></div>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f'<div class="glass-card"><div class="label">🔒 PII 脱敏</div>'
        f'<div class="value">{d_on}</div>'
        f'<div class="sub">姓名 / 手机 / 邮箱 等敏感字段</div></div>',
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f'<div class="glass-card"><div class="label">📚 简历库</div>'
        f'<div class="value">{stats0["total"]} 人</div>'
        f'<div class="sub">{len(stats0["by_department"])} 个部门 · {len(stats0["by_language"])} 种语言</div></div>',
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        f'<div class="glass-card"><div class="label">🌐 配置库</div>'
        f'<div class="value">{len(LANG_NAMES)} 语种</div>'
        f'<div class="sub">{len(DEPT_NAMES)} 个部门 · 全部可 DIY</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs([
    "📋  JD 匹配评分",
    "📚  简历库管理",
    "⚙️  管理员设置",
])


# ===================================================================
# Tab 1 · JD 匹配评分
# ===================================================================
with tab1:
    left, right = st.columns([1, 1])

    with left:
        st.subheader("① 岗位描述 (JD)")
        jd_source = st.radio("输入方式", ["✍️ 手动粘贴", "📁 上传示例 JD"], horizontal=True, label_visibility="collapsed")
        if jd_source == "📁 上传示例 JD":
            sample_jd_path = get_root() / "data" / "samples" / "sample_jd.txt"
            default_jd = sample_jd_path.read_text(encoding="utf-8") if sample_jd_path.exists() else ""
        else:
            default_jd = ""
        jd_text = st.text_area("JD 内容", value=default_jd, height=220,
                                placeholder="例如：招聘高级 Python 后端工程师，5 年以上经验...",
                                label_visibility="collapsed")

        st.subheader("② 必备技能（多选）")
        selected_skills: list[str] = []
        categories = taxonomy["categories"]
        cat_names = list(categories.keys())
        sk_tabs = st.tabs(cat_names)
        for stab, cat_name in zip(sk_tabs, cat_names):
            with stab:
                skills = categories[cat_name]
                cols = st.columns(3)
                for i, sk in enumerate(skills):
                    with cols[i % 3]:
                        if st.checkbox(sk, key=f"sk_{cat_name}_{sk}"):
                            selected_skills.append(sk)
        if selected_skills:
            st.success(f"✅ 已选 {len(selected_skills)} 项必备技能")

        st.subheader("③ 语言要求（多选）")
        st.caption("勾选岗位需要的语言并选择最低等级。")
        required_languages: list[dict] = []
        lcols = st.columns(2)
        for idx, lname in enumerate(LANG_NAMES):
            with lcols[idx % 2]:
                row = st.columns([1, 1])
                with row[0]:
                    chk = st.checkbox(lname, key=f"lang_{lname}")
                with row[1]:
                    lvl = st.selectbox(" ", LANG_LEVELS, index=1, key=f"lvl_{lname}",
                                       label_visibility="collapsed", disabled=not chk)
                if chk:
                    required_languages.append({"name": lname, "min_level": lvl})

    with right:
        st.subheader("④ 简历来源")
        src = st.radio("选择来源", ["📤 临时上传", "🗂️ 从简历库选人"], horizontal=True)

        uploaded_files = []
        sample_resumes: list[ResumeInput] = []
        picked_records = []

        if src == "📤 临时上传":
            uploaded_files = st.file_uploader(
                "支持 PDF / DOCX / TXT，可一次上传多份",
                type=["pdf", "docx", "txt", "md"], accept_multiple_files=True,
            )
            use_samples = st.checkbox("📁 使用示例简历进行体验", value=not uploaded_files)
            if use_samples:
                sample_dir = get_root() / "data" / "samples" / "sample_resumes"
                if sample_dir.exists():
                    for p in sorted(sample_dir.iterdir()):
                        if p.suffix.lower() in (".pdf", ".docx", ".txt", ".md"):
                            sample_resumes.append(ResumeInput(filename=p.name, file=p))
                    st.info(f"已加载 {len(sample_resumes)} 份示例简历")
        else:
            st.caption("先按部门 / 语言筛选，再从结果中选择参与匹配的人员。")
            dept_filter = st.multiselect("筛选部门", DEPT_NAMES, default=[])
            lang_filter = st.multiselect("必须掌握的语言", LANG_NAMES, default=[])
            kw = st.text_input("关键字（姓名 / 技能 / 部门）", "")
            cand_records = lib.filter_records(
                departments=dept_filter or None,
                must_languages=lang_filter or None,
                keyword=kw,
            )
            st.info(f"匹配到 {len(cand_records)} 份简历")
            if cand_records:
                opts = {f"{r.display_name} · {r.department}": r for r in cand_records}
                sel = st.multiselect("选择参与评分的人员（默认全选）",
                                     list(opts.keys()), default=list(opts.keys()))
                picked_records = [opts[s] for s in sel]

        st.subheader("⑤ 评分参数")
        threshold = st.slider("通过门槛分数", 0, 100, cfg["scoring"].get("min_score_threshold", 60))
        top_n = st.slider("展示 Top N", 1, 50, 10)

    st.markdown("---")
    can_run = bool(jd_text.strip()) and (
        uploaded_files or sample_resumes or picked_records
    )
    run_btn = st.button("🚀 开始 AI 评分", type="primary",
                         width="stretch", disabled=not can_run)

    if run_btn:
        progress_bar = st.progress(0.0)
        status = st.empty()

        def _cb(msg, pct):
            progress_bar.progress(pct)
            status.info(msg)

        with st.spinner("AI 团队工作中..."):
            if src == "🗂️ 从简历库选人":
                result = run_from_library(
                    jd_text=jd_text,
                    records=picked_records,
                    required_skill_filter=selected_skills or None,
                    required_languages=required_languages or None,
                    progress_cb=_cb,
                )
            else:
                if uploaded_files:
                    resume_inputs = [ResumeInput(filename=f.name, file=io.BytesIO(f.getvalue()))
                                     for f in uploaded_files]
                else:
                    resume_inputs = sample_resumes
                result = run_pipeline(
                    jd_text=jd_text, resumes=resume_inputs,
                    required_skill_filter=selected_skills or None,
                    required_languages=required_languages or None,
                    progress_cb=_cb,
                )

        status.success(f"✅ 完成！报告已保存到 `{result.report_path}`")
        progress_bar.empty()

        st.markdown("## 📊 评分结果")
        rows = []
        for c in result.candidates:
            if "error" in c:
                rows.append({"姓名": c["file"], "部门": c.get("department", "—"),
                             "总分": 0, "状态": "❌ " + c["error"]})
                continue
            m = c["match"]
            d = m["dimensions"]

            matched_l = ", ".join(_fmt_lang(x, "level") for x in m.get("matched_languages", []))
            missing_l = ", ".join(_fmt_lang(x, "min_level") for x in m.get("missing_languages", []))
            rows.append({
                "姓名": c["file"],
                "部门": c.get("department", "—"),
                "总分": m["total_score"],
                "置信度": m.get("confidence", 0),
                "硬技能": d.get("hard_skill", 0),
                "经验": d.get("experience", 0),
                "语言": d.get("language", 0),
                "软技能": d.get("soft_skill", 0),
                "学历": d.get("education", 0),
                "匹配技能": ", ".join(m.get("matched_skills", [])),
                "缺失技能": ", ".join(m.get("missing_skills", [])),
                "匹配语言": matched_l,
                "缺失语言": missing_l,
                "推荐理由": m.get("recommendation", ""),
            })
        df = pd.DataFrame(rows).sort_values("总分", ascending=False).head(top_n).reset_index(drop=True)
        df["状态"] = df["总分"].apply(lambda s: _status_label(s, threshold))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("候选人总数", len(result.candidates))
        m2.metric("达标人数", int((df["总分"] >= threshold).sum()))
        m3.metric("最高分", df["总分"].max() if not df.empty else 0)
        m4.metric("平均分", round(df["总分"].mean(), 1) if not df.empty else 0)

        st.dataframe(df, width="stretch", hide_index=True)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button("📥 下载 Markdown 报告", data=result.report_md,
                                file_name=result.report_path.name if result.report_path else "report.md",
                                mime="text/markdown", width="stretch")
        with col_d2:
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 下载 CSV 排序表", data=csv,
                                file_name="ranking.csv", mime="text/csv",
                                width="stretch")

        with st.expander("📄 查看完整报告"):
            st.markdown(result.report_md)
        with st.expander("🔍 查看 JD 解析结果"):
            st.json(result.jd)
        _render_result_details(result.candidates, threshold)


# ===================================================================
# Tab 2 · 简历库管理
# ===================================================================
with tab2:
    st.subheader("📥 批量导入简历到人才库")
    imp_col1, imp_col2 = st.columns([2, 1])
    with imp_col1:
        imp_files = st.file_uploader(
            "选择简历（PDF / DOCX / TXT），可多选",
            type=["pdf", "docx", "txt", "md"], accept_multiple_files=True,
            key="lib_upload",
        )
    with imp_col2:
        imp_dept = st.selectbox("归属部门", DEPT_NAMES, key="imp_dept")

    if st.button("🚀 开始导入", type="primary", disabled=not imp_files):
        prog = st.progress(0.0)
        ok, fail = 0, 0
        for i, f in enumerate(imp_files):
            prog.progress((i + 1) / len(imp_files))
            try:
                lib.import_resume(
                    file=io.BytesIO(f.getvalue()),
                    filename=f.name,
                    department=imp_dept,
                    desensitize_enabled=cfg["desensitize"]["enabled"],
                )
                ok += 1
            except Exception as e:
                st.warning(f"❌ {f.name} 导入失败：{e}")
                fail += 1
        prog.empty()
        st.success(f"完成：成功 {ok} 份，失败 {fail} 份")
        st.rerun()

    st.markdown("---")
    st.subheader("📚 当前简历库")

    stats1 = lib.stats()
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("总人数", stats1["total"])
    s2.metric("覆盖部门数", len(stats1["by_department"]))
    s3.metric("覆盖语言数", len(stats1["by_language"]))
    s4.metric("已反馈人数", stats1.get("by_feedback", {}).get("未反馈", 0) and stats1["total"] - stats1.get("by_feedback", {}).get("未反馈", 0) or 0)

    if stats1["by_department"]:
        with st.expander("📊 按部门分布"):
            st.bar_chart(pd.Series(stats1["by_department"]))
    if stats1["by_language"]:
        with st.expander("🌐 按语言分布"):
            st.bar_chart(pd.Series(stats1["by_language"]))
    if stats1.get("by_feedback"):
        with st.expander("🗳️ 反馈状态分布"):
            st.bar_chart(pd.Series(stats1["by_feedback"]))

    _render_feedback_metrics()

    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    with fcol1:
        f_dept = st.multiselect("筛选部门", DEPT_NAMES, key="f_dept")
    with fcol2:
        f_lang = st.multiselect("必须包含语言", LANG_NAMES, key="f_lang")
    with fcol3:
        f_kw = st.text_input("关键字", "", key="f_kw")
    with fcol4:
        f_feedback = st.multiselect("反馈状态", FEEDBACK_OPTIONS, key="f_feedback")

    records = lib.filter_records(f_dept or None, f_lang or None, f_kw)
    if f_feedback:
        feedback_set = set(f_feedback)
        records = [r for r in records if r.feedback_status in feedback_set]

    if not records:
        st.info("当前条件下无记录。")
    else:
        rows = []
        for r in records:
            rows.append({
                "ID": r.id,
                "姓名": r.display_name,
                "部门": r.department,
                "语言": ", ".join(f'{l["name"]}({l.get("level","")})' for l in r.languages),
                "技能数": len(r.parsed.get("hard_skills", [])),
                "反馈状态": r.feedback_status,
                "反馈时间": r.feedback_updated_at or "—",
                "导入时间": r.imported_at,
                "来源文件": r.source_file,
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        st.markdown("#### ✏️ 编辑 / 删除单条记录")
        rec_map = {f"{r.display_name} ({r.id})": r for r in records}
        pick = st.selectbox("选择一条记录", list(rec_map.keys()))
        if pick:
            rec = rec_map[pick]
            ec1, ec2 = st.columns(2)
            with ec1:
                new_name = st.text_input("姓名", rec.display_name, key=f"ed_n_{rec.id}")
                new_dept = st.selectbox("部门", DEPT_NAMES,
                                         index=DEPT_NAMES.index(rec.department) if rec.department in DEPT_NAMES else 0,
                                         key=f"ed_d_{rec.id}")
            with ec2:
                new_notes = st.text_area("备注", rec.notes, key=f"ed_no_{rec.id}", height=100)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("💾 保存修改", key=f"sv_{rec.id}", width="stretch"):
                    lib.update_record(rec.id, display_name=new_name,
                                       department=new_dept, notes=new_notes)
                    st.success("已保存")
                    st.rerun()
            with b2:
                if st.button("🗑️ 删除", key=f"del_{rec.id}", type="secondary", width="stretch"):
                    lib.delete_record(rec.id)
                    st.warning("已删除")
                    st.rerun()

            with st.expander("🔍 查看解析详情"):
                st.json(rec.parsed)

            st.markdown("#### 🗳️ 人工反馈闭环")
            fb1, fb2 = st.columns([1, 1.5])
            with fb1:
                current_idx = FEEDBACK_OPTIONS.index(rec.feedback_status) if rec.feedback_status in FEEDBACK_OPTIONS else 0
                feedback_status = st.selectbox(
                    "反馈结论",
                    FEEDBACK_OPTIONS,
                    index=current_idx,
                    key=f"fb_status_{rec.id}",
                )
                st.caption(f"最近更新时间：{rec.feedback_updated_at or '暂无'}")
            with fb2:
                feedback_note = st.text_area(
                    "反馈说明",
                    rec.feedback_note,
                    key=f"fb_note_{rec.id}",
                    height=110,
                    placeholder="例如：面试通过，项目深度符合预期；或：关键词匹配高，但实操深度不足。",
                )
            if st.button("💾 保存反馈", key=f"fb_save_{rec.id}", width="stretch"):
                lib.update_feedback(rec.id, feedback_status, feedback_note)
                st.success("反馈已保存，可用于后续试点评测和规则校准。")
                st.rerun()

            if rec.feedback_history:
                with st.expander("🕘 查看反馈历史"):
                    st.dataframe(pd.DataFrame(rec.feedback_history[::-1]), width="stretch", hide_index=True)


# ===================================================================
# Tab 3 · 语言 & 部门管理（管理员 DIY）
# ===================================================================
with tab3:
    # ============ 🤖 LLM 模型选择（管理员） ============
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#f0f4ff,#fdf2ff);
                    padding:18px 22px;border-radius:14px;margin-bottom:14px;
                    border-left:4px solid #764ba2;">
            <h3 style="margin:0;color:#1e293b;">🤖 LLM 模型选择中心</h3>
            <p style="margin:6px 0 0 0;color:#475569;font-size:13px;">
                按分组下拉切换底层 AI 引擎 · 支持
                <b style="color:#b91c1c">国产 5 大</b> ·
                <b style="color:#15803d">本地私有部署</b> ·
                <b style="color:#1d4ed8">国际云服务</b> ·
                <b style="color:#92400e">离线 Mock</b>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    catalog = get_models_catalog()
    providers = catalog.get("providers", [])
    if not providers:
        st.error("⚠️ 未找到模型目录 config/models_catalog.json，请检查项目完整性。")
        st.stop()

    llm_cfg = dict(cfg.get("llm", {}))
    cur_provider = llm_cfg.get("provider") or llm_cfg.get("mode") or catalog.get("default_provider", "deepseek")

    provider_ids = [p["id"] for p in providers]
    if cur_provider not in provider_ids:
        cur_provider = provider_ids[0]

    # 标签函数：把 emoji + 分组 + 名字组合
    def _fmt_prov(pid: str) -> str:
        p = next((x for x in providers if x["id"] == pid), {})
        return f"{p.get('emoji','')} {p.get('name', pid)}  ·  [{p.get('group','')}]"

    # ----- 1. 模型供应商分组下拉 -----
    new_provider = st.selectbox(
        "🎯 选择模型供应商（按分组）",
        options=provider_ids,
        index=provider_ids.index(cur_provider),
        format_func=_fmt_prov,
        key="llm_provider_pick",
    )
    prov = get_provider(new_provider) or {}
    api_type = prov.get("api_type", "mock")

    # ----- 2. 当前模型信息卡 -----
    tag_class = {
        "国产 · 在线": "tag-cn",
        "本地 · 私有部署": "tag-local",
        "国际 · 云服务": "tag-intl",
        "演示 · 离线": "tag-demo",
    }.get(prov.get("group", ""), "tag-demo")

    st.markdown(
        f"""
        <div class="model-card">
            <div class="head">
                {prov.get('emoji','')} {prov.get('name','-')}
                <span class="tag {tag_class}">{prov.get('group','')}</span>
            </div>
            <div style="color:#475569;font-size:13px;margin-top:6px;">{prov.get('tagline','')}</div>
            <div style="color:#64748b;font-size:12px;margin-top:8px;">
                🌐 <code>{prov.get('api_base') or '（Azure 由用户填写 endpoint）'}</code>
            </div>
            <div style="color:#64748b;font-size:12px;margin-top:4px;">
                🔑 {prov.get('key_hint','-')}
            </div>
            <div style="color:#64748b;font-size:12px;margin-top:4px;">
                📚 {prov.get('docs','-')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----- 3. 本地模式额外一键自检 -----
    if api_type == "openai_compatible" and prov.get("no_key"):
        st.info(
            f"🏠 **本地模式**：先确保本地服务已在 `{prov.get('api_base')}` 启动。"
            f"你可以通过下方"
            f"「💾 保存」或「🧪 保存并连接测试」来验证。"
        )

    # ----- 4. 配置表单 -----
    with st.form("llm_form", clear_on_submit=False):
        # 模型下拉
        model_options = list(prov.get("models", []) or [prov.get("default_model", "")])
        same_provider = new_provider == (llm_cfg.get("provider") or llm_cfg.get("mode"))
        if same_provider:
            cur_model = llm_cfg.get("model") or prov.get("default_model") or model_options[0]
        else:
            cur_model = prov.get("default_model") or model_options[0]
        if cur_model not in model_options:
            model_options = [cur_model] + model_options

        model_name = st.selectbox(
            "📦 选择模型",
            options=model_options,
            index=model_options.index(cur_model),
            help="若想新增模型名，直接编辑 config/models_catalog.json 即可。",
        )

        # 字段按 api_type 切换
        api_key = ""
        api_base = prov.get("api_base", "")
        azure_endpoint = ""
        azure_deployment = ""
        azure_api_version = ""

        if api_type == "mock":
            st.success("🧪 Mock 模式无需任何配置，直接使用本地规则模拟 LLM 输出。")
        elif api_type == "openai_compatible":
            need_key = not prov.get("no_key", False)
            api_key = st.text_input(
                "🔑 API Key" + (" （本地模式可留空）" if not need_key else ""),
                value=llm_cfg.get("api_key", "") if same_provider else "",
                type="password",
                placeholder="留空 = 本地服务无鉴权" if not need_key else "粘贴你的 sk-xxxx",
            )
            api_base = st.text_input(
                "🌐 API Base URL",
                value=(llm_cfg.get("api_base") if same_provider else prov.get("api_base", "")) or prov.get("api_base", ""),
                help="可改写为自建网关 / 反向代理 / 局域网内网地址。",
            )
        elif api_type == "azure_openai":
            azure_endpoint = st.text_input(
                "🌐 Azure Endpoint",
                value=llm_cfg.get("azure_endpoint", ""),
                placeholder="https://your-resource.openai.azure.com/",
            )
            api_key = st.text_input(
                "🔑 Azure API Key",
                value=llm_cfg.get("azure_api_key", ""),
                type="password",
            )
            azure_deployment = st.text_input(
                "📌 部署名（Deployment）",
                value=llm_cfg.get("azure_deployment", model_name),
                help="Azure 上你创建的部署名，可与模型名不同。",
            )
            azure_api_version = st.text_input(
                "🗓 API Version",
                value=llm_cfg.get("azure_api_version", "2024-08-01-preview"),
            )

        # 通用参数
        tc1, tc2 = st.columns(2)
        with tc1:
            temp = st.slider("🌡 Temperature", 0.0, 1.5,
                             float(llm_cfg.get("temperature", 0.2)), 0.05,
                             disabled=(api_type == "mock"))
        with tc2:
            mx = st.number_input("📏 Max Tokens", 256, 16000,
                                 int(llm_cfg.get("max_tokens", 2000)), 128,
                                 disabled=(api_type == "mock"))

        bsave, btest = st.columns(2)
        with bsave:
            do_save = st.form_submit_button("💾 保存配置", width="stretch")
        with btest:
            do_test = st.form_submit_button("🧪 保存并连接测试", width="stretch")

    if do_save or do_test:
        err = None
        if api_type == "openai_compatible" and not prov.get("no_key") and not api_key.strip():
            err = f"{prov.get('name')} 需要填写 API Key 才能调用真实模型。"
        elif api_type == "azure_openai" and not (azure_endpoint.strip() and api_key.strip() and azure_deployment.strip()):
            err = "Azure OpenAI 需要 Endpoint / API Key / 部署名都不为空。"

        if err:
            st.error(f"❌ {err}")
        else:
            new_cfg = dict(cfg)
            new_llm = {
                "provider": new_provider,
                "mode": "azure_openai" if api_type == "azure_openai" else ("mock" if api_type == "mock" else new_provider),
                "model": model_name,
                "api_key": api_key.strip(),
                "api_base": (api_base or prov.get("api_base", "")).strip(),
                "azure_endpoint": azure_endpoint.strip(),
                "azure_api_key": api_key.strip() if api_type == "azure_openai" else llm_cfg.get("azure_api_key", ""),
                "azure_deployment": azure_deployment.strip(),
                "azure_api_version": azure_api_version.strip() or "2024-08-01-preview",
                "temperature": float(temp),
                "max_tokens": int(mx),
            }
            new_cfg["llm"] = new_llm

            try:
                save_config(new_cfg)
                reload_config()
                llm_client.reset_client()
            except Exception as e:
                st.error(f"❌ 保存失败：{type(e).__name__}: {e}")
                st.stop()

            st.success(f"✅ 已保存。当前模型：**{prov.get('emoji','')} {prov.get('name')}** · `{model_name}`")

            if do_test:
                with st.spinner(f"正在连接 {prov.get('name')} ..."):
                    try:
                        cli = llm_client.get_llm_client()
                        out = cli.chat_json(
                            "你是 JSON 测试器，必须返回 JSON。",
                            '请回复：{"ok": true, "model": "<your-name>", "msg": "hello"}',
                        )
                        if "_error" in out:
                            tip = ""
                            if prov.get("no_key"):
                                tip = f"\n\n💡 本地模式排查：\n1. 服务是否启动？\n2. 端口是否匹配 `{prov.get('api_base')}`？\n3. 模型是否已下载（如 `ollama pull {model_name}`）？"
                            st.error(f"❌ 连接失败：{out.get('_error')}  \n返回：`{out.get('_raw','')[:200]}`{tip}")
                        else:
                            st.success(f"✅ 连接成功！模型返回：`{out}`")
                    except Exception as e:
                        st.error(f"❌ 连接失败：{type(e).__name__}: {e}")
            else:
                st.rerun()

    st.markdown("---")

    # ============ 语言 & 部门 ============
    st.subheader("🌐 语言 & 部门 DIY")
    st.caption("可在此添加自定义语言（如其它小语种）和组织部门。内置项受保护，不可删除。")
    col_lang, col_dept = st.columns(2)

    with col_lang:
        st.subheader("🌐 语言库")
        lrows = []
        for l in lang_cfg["languages"]:
            lrows.append({
                "名称": l["name"], "代码": l.get("code", "—"),
                "类型": "内置" if l.get("builtin") else "自定义",
            })
        st.dataframe(pd.DataFrame(lrows), width="stretch", hide_index=True)

        with st.form("add_lang"):
            st.markdown("**➕ 新增语言**")
            n = st.text_input("名称 *（如：荷兰语）")
            c = st.text_input("ISO 代码（如：nl）")
            if st.form_submit_button("添加", width="stretch"):
                if not n.strip():
                    st.error("请填写名称")
                elif any(x["name"] == n for x in lang_cfg["languages"]):
                    st.error("已存在")
                else:
                    lang_cfg["languages"].append({"name": n.strip(), "code": c.strip(), "builtin": False})
                    save_languages(lang_cfg)
                    st.success(f"已添加：{n}")
                    st.rerun()

        st.markdown("**🗑️ 删除自定义语言**")
        custom_langs = [l["name"] for l in lang_cfg["languages"] if not l.get("builtin")]
        if custom_langs:
            to_del = st.selectbox("选择", custom_langs, key="del_lang_pick")
            if st.button("删除该语言", key="del_lang_btn"):
                lang_cfg["languages"] = [l for l in lang_cfg["languages"] if l["name"] != to_del]
                save_languages(lang_cfg)
                st.warning(f"已删除：{to_del}")
                st.rerun()
        else:
            st.caption("（暂无自定义语言）")

    with col_dept:
        st.subheader("🏢 组织部门")
        drows = []
        for d in dept_cfg["departments"]:
            drows.append({
                "名称": d["name"],
                "类型": "内置" if d.get("builtin") else "自定义",
            })
        st.dataframe(pd.DataFrame(drows), width="stretch", hide_index=True)

        with st.form("add_dept"):
            st.markdown("**➕ 新增部门**")
            nd = st.text_input("部门名称 *")
            if st.form_submit_button("添加", width="stretch"):
                if not nd.strip():
                    st.error("请填写名称")
                elif any(x["name"] == nd for x in dept_cfg["departments"]):
                    st.error("已存在")
                else:
                    dept_cfg["departments"].append({"name": nd.strip(), "builtin": False})
                    save_departments(dept_cfg)
                    st.success(f"已添加：{nd}")
                    st.rerun()

        st.markdown("**🗑️ 删除自定义部门**")
        custom_depts = [d["name"] for d in dept_cfg["departments"] if not d.get("builtin")]
        if custom_depts:
            to_del_d = st.selectbox("选择", custom_depts, key="del_dept_pick")
            if st.button("删除该部门", key="del_dept_btn"):
                dept_cfg["departments"] = [d for d in dept_cfg["departments"] if d["name"] != to_del_d]
                save_departments(dept_cfg)
                st.warning(f"已删除：{to_del_d}")
                st.rerun()
        else:
            st.caption("（暂无自定义部门）")

    st.markdown("---")
    _render_governance_panel()


# ---------------- 侧边栏 ----------------
with st.sidebar:
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#667eea,#764ba2);
                    padding:14px 16px;border-radius:12px;color:white;margin-bottom:14px;">
            <div style="font-size:18px;font-weight:700;">🎯 TalentScope</div>
            <div style="font-size:11px;opacity:.85;">v1.2 · 多模型 / 本地优先</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 🚀 当前引擎")
    st.markdown(
        f"""
        <div style="background:#f8fafc;padding:12px;border-radius:10px;
                    border-left:3px solid #764ba2;font-size:13px;line-height:1.7;">
            <b>{_prov_name}</b><br>
            <span style="color:#64748b;">📦 {_model_name}</span><br>
            <span style="color:#94a3b8;font-size:11px;">{_prov_group}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### ✨ 亮点")
    st.markdown(
        """
        - 🤖 **10+ 模型一键切换**（国产 / 本地 / 国际）
        - 🏠 **本地优先**：Ollama / LM Studio / vLLM
        - 🔒 PII 全程脱敏
        - 📊 5 维加权评分（含语言）
        - 🗂️ 持久化简历库 + DIY 部门/语种
        - 📄 一键 Markdown / Excel 报告
        """
    )

    st.markdown("### ⚙️ 操作")
    if st.button("🔄 重新加载配置", width="stretch"):
        llm_client.reset_client()
        reload_config()
        st.cache_data.clear()
        st.success("已重置")
        st.rerun()

    if st.button("📂 打开输出目录", width="stretch"):
        import os
        out = get_root() / cfg["storage"]["output_dir"]
        if sys.platform == "win32":
            os.startfile(out)
        st.info(f"目录：{out}")
