"""
私有知识库加载器 — 安全隔离层

加载策略:
  1. 优先从 ~/.ielts-grader-private/ 加载完整知识库（你自己保留）
  2. 回退到内置 lite 版（公开 repo 只有演示级数据）

这样公开 repo 只有骨架，竞品 clone 也拿不到核心 IP。
"""

import json, os
from pathlib import Path

_PRIVATE_DIR = Path.home() / ".ielts-grader-private"


def _load_json(filename: str) -> dict:
    """从私有目录加载 JSON 文件"""
    path = _PRIVATE_DIR / filename
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _has_private_data() -> bool:
    """检查是否配置了完整知识库"""
    return (_PRIVATE_DIR / "band_profiles.json").exists()


# ═══════════════════════════════════════════════════════════
# 公开版 Lite 知识库（仅展示用途，足够运行演示）
# ═══════════════════════════════════════════════════════════

LITE_BAND_PROFILES = {
    "5.0": {
        "label": "能用但局限 ⚠️高原期",
        "overall": "最常见高原平台期。基础已建立但错误固化——需要纠正而非学新。",
        "priority": "⚠️错误歼灭战+衔接词升级+复杂句成功率。"
    }
}

LITE_WRITING_STRATEGIES = {
    "5.0": {
        "band_label": "Band 5 ⚠️高原期",
        "action": "错误歼灭战: 收集3篇旧作文→统计Top3错误→专盯这3类。衔接词升级。",
        "focus_4weeks": "第1周: 错误模式诊断。第2周: 只盯Top3错误。第3周: 衔接词升级。第4周: 综合检验。"
    }
}

LITE_ROADMAPS = {
    "5.0→6.0": {
        "duration": "2-6个月 ⚠️高原突破",
        "goal": "固化错误降50% | 复杂句成功率30%→60%+ | 衔接词自然多样",
        "phase_4weeks": [
            {"周": 1, "焦点": "错误模式诊断", "任务": "收集过去3篇T2作文→逐句标记语法错误→统计Top3错误类型。", "检验": "完成错误类型统计表"},
            {"周": 2, "焦点": "Top3错误歼灭", "任务": "只盯Top3错误写作×3篇，写完只检查这3类。", "检验": "Top3错误频率下降30%"},
            {"周": 3, "焦点": "复杂句成功率", "任务": "一稿二写法×3次，每篇3-5个正确复杂句。", "检验": "复杂句成功率≥40%"},
            {"周": 4, "焦点": "综合检验", "任务": "T1+T2限时模写60min。", "检验": "Top3错误降≥40% | 衔接词≥5种 | 复杂句≥3个正确"}
        ]
    }
}


def get_band_profiles() -> dict:
    """获取 Band 画像数据"""
    data = _load_json("band_profiles.json")
    if data:
        return data
    return LITE_BAND_PROFILES


def get_writing_strategies() -> dict:
    """获取写作策略数据"""
    data = _load_json("writing_strategies.json")
    if data:
        return data
    return LITE_WRITING_STRATEGIES


def get_writing_roadmaps() -> dict:
    """获取路线图数据"""
    data = _load_json("writing_roadmaps.json")
    if data:
        return data
    return LITE_ROADMAPS
