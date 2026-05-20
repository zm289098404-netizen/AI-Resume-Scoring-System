"""
Tkinter 桌面配置向导
====================
首次运行时弹出图形化界面，让用户选择 LLM 模式并输入 Azure 配置。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox


def launch_wizard(default: dict) -> dict:
    """启动向导，返回最终配置 dict"""
    result: dict = {"cfg": None}

    root = tk.Tk()
    root.title("TalentScope 配置向导")
    root.geometry("620x560")
    root.resizable(False, False)

    # 居中
    root.update_idletasks()
    w, h = 620, 560
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    # ---- 样式 ----
    style = ttk.Style()
    try:
        style.theme_use("vista")
    except tk.TclError:
        pass
    style.configure("Title.TLabel", font=("Microsoft YaHei", 16, "bold"))
    style.configure("Sub.TLabel", font=("Microsoft YaHei", 9), foreground="#666")
    style.configure("Section.TLabel", font=("Microsoft YaHei", 10, "bold"))

    # ---- 顶部标题 ----
    header = ttk.Frame(root, padding=(20, 20, 20, 10))
    header.pack(fill="x")
    ttk.Label(header, text="TalentScope 配置向导", style="Title.TLabel").pack(anchor="w")
    ttk.Label(header, text="首次运行需要做一次性配置，之后将不再弹出",
              style="Sub.TLabel").pack(anchor="w", pady=(4, 0))

    ttk.Separator(root).pack(fill="x", padx=20)

    # ---- 主体 ----
    body = ttk.Frame(root, padding=(20, 15, 20, 10))
    body.pack(fill="both", expand=True)

    # === 1. LLM 模式 ===
    ttk.Label(body, text="① 选择 LLM 模式", style="Section.TLabel").pack(anchor="w")
    mode_var = tk.StringVar(value=default["llm"]["mode"] or "mock")

    mode_frame = ttk.Frame(body)
    mode_frame.pack(fill="x", pady=(6, 12))

    rb1 = ttk.Radiobutton(mode_frame, text="🌐 Azure OpenAI（真实调用，需要 API Key）",
                          variable=mode_var, value="azure_openai")
    rb1.pack(anchor="w")
    rb2 = ttk.Radiobutton(mode_frame, text="🧪 Mock 模式（无需 Key，立即体验完整流程）",
                          variable=mode_var, value="mock")
    rb2.pack(anchor="w", pady=(4, 0))

    # === 2. Azure 配置（动态启用/禁用） ===
    azure_frame = ttk.LabelFrame(body, text="② Azure OpenAI 配置", padding=(12, 8))
    azure_frame.pack(fill="x", pady=(0, 12))

    entries: dict[str, tk.Entry] = {}
    fields = [
        ("Endpoint", "azure_endpoint", "https://your-resource.openai.azure.com/"),
        ("API Key", "azure_api_key", ""),
        ("部署名", "azure_deployment", "gpt-4o"),
        ("API 版本", "azure_api_version", "2024-08-01-preview"),
    ]
    for i, (label, key, hint) in enumerate(fields):
        ttk.Label(azure_frame, text=label + ":", width=12).grid(row=i, column=0, sticky="w", pady=3)
        e = ttk.Entry(azure_frame, width=55,
                      show="*" if key == "azure_api_key" else "")
        e.insert(0, default["llm"].get(key, "") or hint if key != "azure_api_key" else "")
        if key == "azure_endpoint" and not default["llm"].get(key):
            e.delete(0, tk.END)
            e.insert(0, hint)
        e.grid(row=i, column=1, sticky="we", pady=3)
        entries[key] = e
    azure_frame.columnconfigure(1, weight=1)

    def _toggle_azure(*_):
        state = "normal" if mode_var.get() == "azure_openai" else "disabled"
        for e in entries.values():
            e.configure(state=state)
    mode_var.trace_add("write", _toggle_azure)
    _toggle_azure()

    # === 3. 脱敏开关 ===
    desens_frame = ttk.LabelFrame(body, text="③ 数据合规", padding=(12, 8))
    desens_frame.pack(fill="x", pady=(0, 12))
    desens_var = tk.BooleanVar(value=default["desensitize"]["enabled"])
    ttk.Checkbutton(desens_frame,
                    text="启用 PII 脱敏（推荐：姓名/电话/邮箱/身份证/地址自动遮罩后再送入 LLM）",
                    variable=desens_var).pack(anchor="w")

    # === 4. 输出目录 ===
    out_frame = ttk.LabelFrame(body, text="④ 输出目录", padding=(12, 8))
    out_frame.pack(fill="x", pady=(0, 12))
    out_var = tk.StringVar(value=default["storage"]["output_dir"])
    ttk.Entry(out_frame, textvariable=out_var).pack(fill="x")

    # ---- 底部按钮 ----
    footer = ttk.Frame(root, padding=(20, 0, 20, 20))
    footer.pack(fill="x", side="bottom")

    def on_save():
        mode = mode_var.get()
        if mode == "azure_openai":
            ep = entries["azure_endpoint"].get().strip()
            key = entries["azure_api_key"].get().strip()
            if not ep or not ep.startswith("https://"):
                messagebox.showerror("配置错误", "请填写有效的 Azure Endpoint")
                return
            if not key:
                messagebox.showerror("配置错误", "请填写 API Key")
                return

        cfg = dict(default)
        cfg["llm"] = {
            "mode": mode,
            "azure_endpoint": entries["azure_endpoint"].get().strip(),
            "azure_api_key": entries["azure_api_key"].get().strip(),
            "azure_deployment": entries["azure_deployment"].get().strip() or "gpt-4o",
            "azure_api_version": entries["azure_api_version"].get().strip() or "2024-08-01-preview",
        }
        cfg["desensitize"]["enabled"] = desens_var.get()
        cfg["storage"]["output_dir"] = out_var.get().strip() or "data/output"
        result["cfg"] = cfg
        root.destroy()

    def on_cancel():
        if messagebox.askyesno("退出", "尚未完成配置，确定退出吗？"):
            root.destroy()

    ttk.Button(footer, text="取消", command=on_cancel).pack(side="right", padx=(8, 0))
    ttk.Button(footer, text="保存并启动", command=on_save).pack(side="right")
    ttk.Label(footer, text="完成后将自动启动 Web 控制台 http://localhost:8501",
              style="Sub.TLabel").pack(side="left")

    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.mainloop()

    if result["cfg"] is None:
        raise SystemExit("用户取消配置")
    return result["cfg"]
