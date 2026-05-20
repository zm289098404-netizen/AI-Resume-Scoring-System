# 🎯 TalentScope · AI 简历智能匹配评分系统

> 博彦科技 2026 AI 大奖参赛项目 · 本地可运行的完整代码库

---

## ✨ 特性

- **🚀 一键启动**：双击 `start.bat`，自动完成环境检测 → 依赖安装 → 配置向导 → UI 启动
- **🖱️ 图形化配置向导**：首次运行自动弹出 Tkinter 桌面向导，配置 LLM 模式
- **🧪 Mock 模式**：无需 Azure 订阅，开箱即可体验完整 4 Agent 流程
- **🌐 真实 LLM**：支持 Azure OpenAI，企业租户内合规调用
- **🔒 PII 全程脱敏**：姓名/电话/邮箱/身份证/地址送入 LLM 前自动遮罩
- **🤖 4 Agent 协作**：JD 解析 → 简历解析 → 匹配评分 → 报告生成
- **🗂️ 技能多选筛选**：按 11 个分类、100+ 技能勾选必备项
- **📊 多维评分 + 风险提示**：硬技能 / 经验 / 软技能 / 学历加权
- **📥 报告下载**：Markdown 报告 + CSV 排序表

---

## 🚀 快速开始

### Windows

```cmd
双击 start.bat
```

首次运行会：
1. 检查 Python（需 3.10+）
2. 自动安装依赖（约 1-3 分钟）
3. 弹出配置向导（选 Mock 模式可立即体验）
4. 启动 Web 控制台（自动打开 http://localhost:8501）

### macOS / Linux

```bash
chmod +x start.sh
./start.sh
```

---

## 📁 项目结构

```
talentscope/
├── start.bat / start.sh        # 一键启动入口
├── bootstrap.py                # 环境检测 + 依赖安装 + 向导
├── bootstrap_wizard.py         # Tkinter 桌面配置向导
├── requirements.txt
├── config/
│   ├── config.example.json     # 配置模板
│   ├── config.json             # 实际配置（首次运行生成，不入库）
│   └── skills_taxonomy.json    # 11 大类 100+ 技能词典
├── src/talentscope/
│   ├── config_loader.py        # 配置加载
│   ├── pipeline.py             # 端到端编排
│   ├── core/
│   │   ├── desensitizer.py     # 🔒 PII 脱敏引擎
│   │   ├── parser.py           # 📄 PDF/DOCX/TXT 解析
│   │   └── llm_client.py       # 🤖 LLM 客户端（Azure / Mock）
│   ├── agents/
│   │   ├── jd_agent.py         # 📋 JD 解析 Agent
│   │   ├── resume_agent.py     # 📄 简历解析 Agent
│   │   ├── match_agent.py      # ⚖️ 匹配评分 Agent
│   │   └── report_agent.py     # 📊 报告生成 Agent
│   └── ui/
│       └── app.py              # 🖥️ Streamlit 控制台
├── data/
│   ├── samples/                # 示例 JD + 5 份示例简历
│   └── output/                 # 生成的报告（自动创建）
└── README.md
```

---

## 🧩 模块化扩展

### 添加新的 Agent

1. 在 `src/talentscope/agents/` 新建 `xxx_agent.py`
2. 实现一个 `parse_xxx()` 或 `analyze_xxx()` 函数，调用 `get_llm_client()`
3. 在 `pipeline.py` 的 `run()` 中接入

### 添加新的技能分类

直接编辑 `config/skills_taxonomy.json`，UI 会自动渲染新的标签页。

### 切换 LLM 提供商

`src/talentscope/core/llm_client.py` 中添加新的 Client 类（如 `OpenAIClient`、`QwenClient`），并在 `get_llm_client()` 工厂中根据 `cfg.llm.mode` 路由。

---

## 🔒 数据合规

| 环节 | 措施 |
|---|---|
| 数据采集 | 用户主动上传，明确告知 |
| 脱敏 | 所有简历进入 LLM 前自动遮罩 PII |
| 传输 | Azure OpenAI 走公司租户 + HTTPS（生产建议加 VNet + Private Endpoint） |
| 存储 | 报告本地保存，配置 `retention_days` 后自动清理 |
| 映射表 | 仅内存中维护，进程结束即销毁 |
| 审计 | 所有调用可加 Azure Monitor 日志（生产环境） |

> 详细合规方案见 `../03-提名材料模板.md` 第六章

---

## 🛠️ 常见问题

**Q: 没装 Python 怎么办？**
访问 https://www.python.org/downloads/ 下载 3.10+，安装时**勾选 "Add Python to PATH"**。

**Q: 配置向导不弹出？**
某些精简版 Python 不带 Tkinter，会自动降级为命令行向导。或在系统重装 Python（官方安装包默认带 Tkinter）。

**Q: Mock 模式和真实 LLM 有什么区别？**
- Mock：基于关键字提取 + 加权评分，**完全确定性**，方便演示和测试
- Azure OpenAI：真实 LLM 推理，**推荐理由更智能**，但需 API Key 且产生费用

**Q: 如何换成本地大模型（Qwen / DeepSeek）？**
在 `llm_client.py` 中仿照 `AzureOpenAIClient` 实现 `OllamaClient` 或 `vLLMClient`，配置 base_url 即可。

**Q: 报告生成在哪里？**
默认 `data/output/report-YYYYMMDD-HHMMSS.md`，UI 上也能直接下载。

---

## 📊 演示步骤（评委 / 客户演示）

1. 双击 `start.bat`，10 秒进入 UI
2. 左侧粘贴示例 JD（或勾选「上传示例 JD」）
3. 勾选必备技能（如 Python / FastAPI / Kubernetes / Azure OpenAI）
4. 右侧勾选「使用示例简历」
5. 点击「🚀 开始 AI 评分」
6. 观察实时进度条 → 排序表 → 下载报告

预计耗时：**Mock 模式 5 秒；Azure OpenAI 模式 20-40 秒**

---

## 📜 License

仅用于博彦科技 2026 AI 大奖参赛与内部演示。

---

*由 Copilot AI Team 协作生成 · 2026-05-20*
