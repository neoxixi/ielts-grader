"""
IELTS 写作批改核心模块 — 知识库 + 启发式评分 + 报告融合
移植自 ielts_eval_demo.py

⚠️ 完整专家知识库存储在 ~/.ielts-grader-private/（不进 git 仓库）
   公开版只有 Band 5 演示数据，完整版请联系商业授权。
"""

import re, json
from typing import Optional

# ═══════════════════════════════════════════
# IELTS 专家知识库（安全隔离）
# 完整版 → ~/.ielts-grader-private/*.json
# 公开版 → _private.py 中的 lite stubs
# ═══════════════════════════════════════════

from ._private import get_band_profiles, get_writing_strategies, get_writing_roadmaps, _has_private_data

IELTS_BAND_PROFILES = get_band_profiles()
IELTS_WRITING_STRATEGIES = get_writing_strategies()
WRITING_ROADMAPS = get_writing_roadmaps()

# 提示用户配置完整知识库（仅首次）
if not _has_private_data():
    import sys
    if not getattr(sys, '_private_warned', False):
        sys._private_warned = True


# ═══════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════

def map_score_to_band_key(overall_band: float) -> str:
    if overall_band is None:
        return "3.0"
    if overall_band <= 3.5: return "3.0"
    elif overall_band <= 4.5: return "4.0"
    elif overall_band <= 5.5: return "5.0"
    elif overall_band <= 6.5: return "6.0"
    else: return "7.0"


def _build_roadmap_key(current_band: float, target_band: float = None) -> str:
    cur_key = map_score_to_band_key(current_band)
    if target_band:
        tgt_key = map_score_to_band_key(target_band)
    else:
        band_val = float(cur_key)
        tgt_key = f"{band_val + 1.0:.1f}" if band_val < 6.0 else "7.0"
    return f"{cur_key}→{tgt_key}"


def ielts_round(raw: float) -> float:
    """IELTS 舍入规则：取最近 0.5"""
    raw = float(raw)
    remainder = raw - int(raw)
    if remainder < 0.25: return float(int(raw))
    elif remainder < 0.75: return int(raw) + 0.5
    else: return float(int(raw) + 1.0)


# ═══════════════════════════════════════════
# 启发式评分器（fallback + 交叉验证）
# ═══════════════════════════════════════════

def heuristic_score(text: str, task_type: str = "T2") -> dict:
    word_count = len(text.split()) if text else 0
    min_words = 150 if task_type == "T1" else 250
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    n_paragraphs = len(paragraphs)
    text_lower = text.lower()

    connector_kw = ["furthermore", "moreover", "however", "therefore", "consequently",
        "for example", "for instance", "in addition", "on the other hand", "in conclusion",
        "firstly", "secondly", "finally", "although", "because", "as a result", "in contrast"]
    connector_count = sum(1 for kw in connector_kw if kw in text_lower)
    template_kw = ["firstly", "secondly", "last but not least",
        "with the development of", "every coin has two sides",
        "in this day and age", "it is widely believed that"]
    template_count = sum(1 for kw in template_kw if kw in text_lower)

    # TA
    ta_base = 4.0
    if word_count >= min_words: ta_base += 1.0
    elif word_count >= min_words * 0.7: ta_base += 0.5
    if n_paragraphs >= 4: ta_base += 1.0
    elif n_paragraphs >= 3: ta_base += 0.5
    ta_band = max(3, min(7, round(ta_base)))

    # CC
    cc_base = 4.0
    if connector_count >= 6: cc_base += 1.5
    elif connector_count >= 4: cc_base += 1.0
    elif connector_count >= 2: cc_base += 0.5
    if template_count >= 3: cc_base -= 1.0
    elif template_count >= 1: cc_base -= 0.5
    cc_band = max(3, min(7, round(cc_base)))

    # LR
    unique_words = len(set(re.findall(r'\b[a-zA-Z]+\b', text_lower))) if text else 0
    lexical_diversity = unique_words / word_count if word_count > 0 else 0
    lr_base = 4.0
    if lexical_diversity > 0.65: lr_base += 1.5
    elif lexical_diversity > 0.55: lr_base += 1.0
    elif lexical_diversity > 0.45: lr_base += 0.5
    lr_band = max(3, min(7, round(lr_base)))

    # GRA
    complex_markers = len(re.findall(
        r'\b(although|because|which|that|whereas|while|despite|unless|provided|if)\b', text_lower))
    gra_base = 4.0
    if complex_markers >= 4: gra_base += 1.0
    elif complex_markers >= 2: gra_base += 0.5
    chinglish = len(re.findall(r'(although\s+.+,\s*but|because\s+.+,\s*so|according to me)', text_lower))
    if chinglish >= 2: gra_base -= 1.0
    elif chinglish >= 1: gra_base -= 0.5
    gra_band = max(3, min(7, round(gra_base)))

    overall = (ta_band + cc_band + lr_band + gra_band) / 4.0
    overall_rounded = round(overall * 2) / 2

    return {
        "dimensions": {
            "TA": {"band": ta_band, "rationale": f"词数{word_count}/{min_words}, 段落{n_paragraphs}"},
            "CC": {"band": cc_band, "rationale": f"衔接词{connector_count}个, 模板标记{template_count}"},
            "LR": {"band": lr_band, "rationale": f"词汇多样性{lexical_diversity:.2f}"},
            "GRA": {"band": gra_band, "rationale": f"复杂标记{complex_markers}个, 中英式{chinglish}"}
        },
        "overall_band": overall_rounded,
        "word_count": word_count,
        "summary": {
            "strengths": ["字数符合要求"] if word_count >= min_words else [],
            "weaknesses": [f"词数不足({word_count}/{min_words})"] if word_count < min_words else [],
            "actionable_tips": [],
            "error_analysis": {}
        }
    }


# ═══════════════════════════════════════════
# 报告融合
# ═══════════════════════════════════════════

def build_enriched_report(llm_result: dict, essay_text: str, task_type: str) -> dict:
    """融合 LLM 评分 + 专家知识库 → 综合报告"""
    dims = llm_result.get("dimensions", {})

    # Fallback 缺失维度
    missing_dims = [k for k in ["TA", "CC", "LR", "GRA"]
                    if k not in dims or dims[k].get("band") is None]
    if missing_dims:
        heu = heuristic_score(essay_text, task_type)
        for k in missing_dims:
            if k in heu.get("dimensions", {}) and heu["dimensions"][k].get("band") is not None:
                dims[k] = heu["dimensions"][k]

    overall = llm_result.get("overall_band", 5.0)
    word_count = llm_result.get("word_count", len(essay_text.split()))
    band_key = map_score_to_band_key(overall)
    profile = IELTS_BAND_PROFILES.get(band_key, {})
    strategy = IELTS_WRITING_STRATEGIES.get(band_key, {})

    current_val = float(band_key)
    target_val = min(current_val + 1.0, 7.0)
    roadmap_key = f"{band_key}→{target_val:.1f}"
    roadmap = WRITING_ROADMAPS.get(roadmap_key, None)
    if roadmap is None:
        known = [k for k in WRITING_ROADMAPS.keys() if k.startswith(band_key)]
        if known:
            roadmap = WRITING_ROADMAPS[known[0]]

    error_analysis = llm_result.get("summary", {}).get("error_analysis", {})
    ai_tips = llm_result.get("summary", {}).get("actionable_tips", [])

    enriched_tips = list(ai_tips)
    if len(enriched_tips) < 3:
        strategy_action = strategy.get("action", "")
        for part in strategy_action.split("。"):
            part = part.strip()
            if part and len(part) > 8:
                enriched_tips.append(part + "。")

    if roadmap and not any(roadmap["phase_4weeks"][0]["焦点"] in t for t in enriched_tips):
        enriched_tips.append(
            f"【第1周焦点】{roadmap['phase_4weeks'][0]['焦点']}：{roadmap['phase_4weeks'][0]['任务']}")

    lr_dim = dims.get("LR", {})
    vocabulary_note = lr_dim.get("rationale", "") or "基于本次写作的词汇表现分析。"

    return {
        "task_type": task_type,
        "word_count": word_count,
        "overall_band": overall,
        "dimensions": dims,
        "band_profile": {
            "band_key": band_key,
            "label": profile.get("label", ""),
            "overall": profile.get("overall", ""),
            "priority": profile.get("priority", ""),
            "vocabulary_note": vocabulary_note,
        },
        "writing_strategy": {
            "band_label": strategy.get("band_label", ""),
            "action": strategy.get("action", ""),
            "focus_4weeks": strategy.get("focus_4weeks", ""),
        },
        "roadmap": {
            "key": roadmap_key,
            "duration": roadmap["duration"] if roadmap else "",
            "goal": roadmap["goal"] if roadmap else "",
            "phase_4weeks": roadmap["phase_4weeks"] if roadmap else [],
        } if roadmap else None,
        "enriched_recommendations": {
            "strengths": llm_result.get("summary", {}).get("strengths", []),
            "weaknesses": llm_result.get("summary", {}).get("weaknesses", []),
            "actionable_tips": enriched_tips[:6],
            "error_analysis": {
                "grammar_top3": error_analysis.get("grammar_top3", []),
                "connector_diversity": error_analysis.get("connector_diversity", ""),
                "template_suspicion": error_analysis.get("template_suspicion", ""),
            }
        }
    }


def build_combined_report(t1_result: dict, t2_result: dict,
                          student: str = "", source: str = "") -> dict:
    """融合 T1 + T2 → 综合写作报告 (T1×1/3 + T2×2/3)"""
    t1_band = t1_result["overall_band"]
    t2_band = t2_result["overall_band"]
    raw_total = t1_band * (1/3) + t2_band * (2/3)
    rounded = ielts_round(raw_total)

    combined_key = map_score_to_band_key(rounded)
    combined_profile = IELTS_BAND_PROFILES.get(combined_key, {})

    t1_tips = t1_result.get("enriched_recommendations", {}).get("actionable_tips", [])
    t2_tips = t2_result.get("enriched_recommendations", {}).get("actionable_tips", [])

    seen_tips = set()
    combined_tips = []
    for tip in t2_tips + t1_tips:
        short = tip[:30]
        if short not in seen_tips:
            seen_tips.add(short)
            combined_tips.append(tip)
        if len(combined_tips) >= 8:
            break

    return {
        "student": student, "source": source, "report_type": "combined",
        "overall_band": rounded,
        "score_breakdown": {
            "task1": {"band": t1_band, "weight": "1/3", "weighted": round(t1_band * 1/3, 3)},
            "task2": {"band": t2_band, "weight": "2/3", "weighted": round(t2_band * 2/3, 3)},
            "raw_total": round(raw_total, 3), "rounded": rounded,
        },
        "band_profile": {
            "band_key": combined_key,
            "label": combined_profile.get("label", ""),
            "overall": combined_profile.get("overall", ""),
            "priority": combined_profile.get("priority", ""),
        },
        "task1": t1_result, "task2": t2_result,
        "cross_task_analysis": {
            "grammar_top3": t2_result.get("enriched_recommendations", {}).get("error_analysis", {}).get("grammar_top3", []),
            "priority_actions": combined_tips[:6],
        }
    }
