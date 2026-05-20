"""配置加载器（单例 + 自动迁移）"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 项目根 = src/talentscope/config_loader.py → 上 3 级
ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "config.json"
CONFIG_EXAMPLE = ROOT / "config" / "config.example.json"
SKILLS_PATH = ROOT / "config" / "skills_taxonomy.json"
LANGUAGES_PATH = ROOT / "config" / "languages.json"
DEPARTMENTS_PATH = ROOT / "config" / "departments.json"
MODELS_CATALOG_PATH = ROOT / "config" / "models_catalog.json"

_cache: dict[str, Any] = {}

DEFAULT_WEIGHTS = {
    "hard_skill": 0.45,
    "experience": 0.20,
    "soft_skill": 0.10,
    "education": 0.10,
    "language": 0.15,
}


def _deep_merge(default: dict, override: dict) -> dict:
    """递归合并：override 优先，缺失字段从 default 补齐"""
    out = dict(default)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def get_config() -> dict:
    if "config" not in _cache:
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {CONFIG_PATH}\n请先运行 start.bat 完成初始化"
            )
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        # 自动迁移：用 example 兜底
        if CONFIG_EXAMPLE.exists():
            with open(CONFIG_EXAMPLE, "r", encoding="utf-8") as f:
                example = json.load(f)
            user_cfg = _deep_merge(example, user_cfg)
        user_cfg.setdefault("scoring", {}).setdefault("weights", {})
        user_cfg["scoring"]["weights"] = _deep_merge(DEFAULT_WEIGHTS, user_cfg["scoring"]["weights"])
        user_cfg.setdefault("storage", {})
        user_cfg["storage"].setdefault("library_dir", "data/resume_library")
        user_cfg["storage"].setdefault("output_dir", "data/output")
        _cache["config"] = user_cfg
    return _cache["config"]


def reload_config() -> None:
    _cache.pop("config", None)


def save_config(cfg: dict) -> None:
    """整体覆盖写回 config.json 并清缓存"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    _cache.pop("config", None)


def get_models_catalog() -> dict:
    """国内主流大模型 + Azure + Mock 的目录。"""
    if "models_catalog" not in _cache:
        if not MODELS_CATALOG_PATH.exists():
            _cache["models_catalog"] = {"default_provider": "mock", "providers": []}
        else:
            with open(MODELS_CATALOG_PATH, "r", encoding="utf-8") as f:
                _cache["models_catalog"] = json.load(f)
    return _cache["models_catalog"]


def save_models_catalog(data: dict) -> None:
    with open(MODELS_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _cache.pop("models_catalog", None)


def get_provider(provider_id: str) -> dict | None:
    catalog = get_models_catalog()
    for p in catalog.get("providers", []):
        if p.get("id") == provider_id:
            return p
    return None


def get_skills_taxonomy() -> dict:
    if "skills" not in _cache:
        with open(SKILLS_PATH, "r", encoding="utf-8") as f:
            _cache["skills"] = json.load(f)
    return _cache["skills"]


def get_languages() -> dict:
    if "languages" not in _cache:
        with open(LANGUAGES_PATH, "r", encoding="utf-8") as f:
            _cache["languages"] = json.load(f)
    return _cache["languages"]


def save_languages(data: dict) -> None:
    with open(LANGUAGES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _cache.pop("languages", None)


def get_departments() -> dict:
    if "departments" not in _cache:
        with open(DEPARTMENTS_PATH, "r", encoding="utf-8") as f:
            _cache["departments"] = json.load(f)
    return _cache["departments"]


def save_departments(data: dict) -> None:
    with open(DEPARTMENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _cache.pop("departments", None)


def get_root() -> Path:
    return ROOT


def get_output_dir() -> Path:
    cfg = get_config()
    p = ROOT / cfg["storage"]["output_dir"]
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_library_dir() -> Path:
    cfg = get_config()
    p = ROOT / cfg["storage"]["library_dir"]
    p.mkdir(parents=True, exist_ok=True)
    return p
