"""
TalentScope Bootstrap
=====================
启动前的环境检查与配置向导。
- 检查 Python 版本
- 检查并自动安装 pip 依赖
- 检查配置文件，若不存在则启动 Tkinter 桌面向导
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "config.json"
CONFIG_EXAMPLE = ROOT / "config" / "config.example.json"
REQUIREMENTS = ROOT / "requirements.txt"

MIN_PY = (3, 10)

# ---------- 颜色输出 ----------
def _c(code: str) -> str:
    return f"\033[{code}m"
OK, WARN, ERR, RST, DIM = _c("32"), _c("33"), _c("31"), _c("0"), _c("90")


def step(msg: str) -> None:
    print(f"\n{DIM}>> {msg}{RST}")


def ok(msg: str) -> None:
    print(f"  {OK}[OK]{RST} {msg}")


def warn(msg: str) -> None:
    print(f"  {WARN}[!]{RST}  {msg}")


def fail(msg: str) -> None:
    print(f"  {ERR}[X]{RST}  {msg}")


# ---------- 检查 1: Python 版本 ----------
def check_python() -> None:
    step("检查 Python 版本")
    ver = sys.version_info
    if (ver.major, ver.minor) < MIN_PY:
        fail(f"Python 版本过低: {ver.major}.{ver.minor}，需要 >= {MIN_PY[0]}.{MIN_PY[1]}")
        sys.exit(1)
    ok(f"Python {ver.major}.{ver.minor}.{ver.micro}")


# ---------- 检查 2: 依赖包 ----------
def _pip_install(args: list[str]) -> None:
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *args]
    subprocess.check_call(cmd)


def check_pip_deps() -> None:
    step("检查 Python 依赖")
    if not REQUIREMENTS.exists():
        fail(f"找不到 {REQUIREMENTS}")
        sys.exit(1)

    # 用快速检测：尝试 import 关键包
    required = {
        "streamlit": "streamlit",
        "pandas": "pandas",
        "pypdf": "pypdf",
        "docx": "python-docx",
        "openai": "openai",
        "dotenv": "python-dotenv",
    }
    missing = []
    for mod, pkg in required.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    if missing:
        warn(f"缺少依赖: {', '.join(missing)}")
        print(f"  {DIM}正在自动安装全部依赖（首次运行约 1-3 分钟）...{RST}")
        try:
            _pip_install(["-r", str(REQUIREMENTS)])
            ok("依赖安装完成")
        except subprocess.CalledProcessError as e:
            fail(f"依赖安装失败: {e}")
            fail("请手动运行: pip install -r requirements.txt")
            sys.exit(1)
    else:
        ok("全部依赖已就绪")


# ---------- 检查 3: 配置文件 / 向导 ----------
def ensure_config() -> dict:
    step("检查配置文件")
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        ok(f"已加载配置: {CONFIG_PATH}")
        # 简单校验
        mode = cfg.get("llm", {}).get("mode", "")
        if mode not in ("azure_openai", "mock"):
            warn("配置不完整，重新启动向导...")
        else:
            return cfg

    warn("未检测到配置文件，启动配置向导...")
    cfg = run_wizard()
    save_config(cfg)
    ok(f"配置已保存到 {CONFIG_PATH}")
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def run_wizard() -> dict:
    """启动 Tkinter 配置向导；若 Tkinter 不可用则降级为 CLI"""
    try:
        import tkinter  # noqa: F401
        from bootstrap_wizard import launch_wizard
        return launch_wizard(default=_load_default_cfg())
    except Exception as e:
        warn(f"GUI 向导不可用 ({e})，使用命令行向导")
        return _cli_wizard()


def _load_default_cfg() -> dict:
    if CONFIG_EXAMPLE.exists():
        with open(CONFIG_EXAMPLE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "llm": {"mode": "mock", "azure_endpoint": "", "azure_api_key": "",
                 "azure_deployment": "gpt-4o", "azure_api_version": "2024-08-01-preview"},
        "desensitize": {"enabled": True, "fields": ["name", "phone", "email", "id_card", "address"]},
        "scoring": {"weights": {"hard_skill": 0.5, "experience": 0.25, "soft_skill": 0.15, "education": 0.1}},
        "storage": {"output_dir": "data/output", "retention_days": 14},
    }


def _cli_wizard() -> dict:
    print("\n" + "=" * 60)
    print(" TalentScope 配置向导（命令行）")
    print("=" * 60)
    print("\n1) Azure OpenAI（真实调用）")
    print("2) Mock 模式（无需 API Key，可立即体验）")
    choice = input("\n请选择 LLM 模式 [2]: ").strip() or "2"
    cfg = _load_default_cfg()
    if choice == "1":
        cfg["llm"]["mode"] = "azure_openai"
        cfg["llm"]["azure_endpoint"] = input("Azure OpenAI Endpoint: ").strip()
        cfg["llm"]["azure_api_key"] = input("API Key: ").strip()
        cfg["llm"]["azure_deployment"] = input("部署名 [gpt-4o]: ").strip() or "gpt-4o"
    else:
        cfg["llm"]["mode"] = "mock"
    return cfg


# ---------- 主流程 ----------
def main() -> None:
    print(f"\n{DIM}TalentScope Bootstrap 启动中...{RST}")
    try:
        check_python()
        check_pip_deps()
        ensure_config()
        ok("环境检查完成，准备启动 UI")
    except KeyboardInterrupt:
        print("\n用户取消")
        sys.exit(130)


if __name__ == "__main__":
    main()
