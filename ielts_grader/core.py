"""
IELTS 写作批改核心模块 — 知识库 + 启发式评分 + 报告融合
移植自 ielts_eval_demo.py
"""

import re, json
from typing import Optional

# ═══════════════════════════════════════════
# IELTS 专家知识库
# ═══════════════════════════════════════════

IELTS_BAND_PROFILES = {
    "3.0": {
        "label": "生存英语水平",
        "overall": "只能应对最简单日常场景，超出基本需求立即无法应对。无时态概念，无法连续说3句完整英语。",
        "priority": "建立基础：词汇+简单句。不做难题。"
    },
    "4.0": {
        "label": "基础但破碎",
        "overall": "能应对熟悉话题但超出舒适区大量错误。时态有意识但70%遗漏。写作中词汇重复率高，缺乏同义替换。",
        "priority": "巩固简单句+积累场景词。"
    },
    "5.0": {
        "label": "能用但局限 ⚠️高原期",
        "overall": "最常见高原平台期。基础已建立但错误固化——需要纠正而非学新。写作中基本词汇够用但同义替换有限。",
        "priority": "⚠️错误歼灭战+衔接词升级+复杂句成功率。高原突破是核心。"
    },
    "6.0": {
        "label": "合格英语使用者",
        "overall": "满足大多数大学和移民门槛。基本自如但仍有不准确处。写作中能使用一定同义替换，但多样性和精确度可提升。",
        "priority": "冲刺6.5+：词汇多样性+论证深度+流利度精进。"
    },
    "7.0": {
        "label": "良好英语使用者",
        "overall": "能处理复杂语言场景，灵活使用复杂结构和词汇。",
        "priority": "保持节奏+微调弱项+扩充academic vocabulary。"
    }
}

IELTS_WRITING_STRATEGIES = {
    "3.0": {
        "band_label": "Band 3 (极有限)",
        "action": "简单句写作每天10句(自我介绍/家乡/昨天做了什么)。语法练习：一般现在时→过去时。不碰复杂句。目标：能写出正确简单句。",
        "focus_4weeks": "第1-2周: 写出完整简单句(主谓宾)。第3-4周: 过去时掌握。每天写5句，用正确时态。"
    },
    "4.0": {
        "band_label": "Band 4 (有限)",
        "action": "T1背4段式模板(引入→概览→细节1→细节2)。T2背4段式结构(引入→Body1→Body2→结论)。写满字数优先(150/250词)。时态一致性训练。",
        "focus_4weeks": "第1-2周: T1结构定型(4段式)。第3-4周: T2 4段式+150词目标。先写够字数，再追质量。"
    },
    "5.0": {
        "band_label": "Band 5 ⚠️高原期",
        "action": "错误歼灭战(前4周核心): 收集3篇旧作文→统计Top3错误→专盯这3类。衔接词升级(淘汰firstly/secondly→用The primary reason is/Furthermore/In contrast)。一稿二写法提升复杂句成功率。PEEL论证结构(P+E至少两步)。",
        "focus_4weeks": "第1周: 错误模式诊断(收集旧作文→统计Top3错误)。第2周: 只盯Top3错误写作。第3周: 衔接词升级+一稿二写。第4周: 综合检验+错题清零。"
    },
    "6.0": {
        "band_label": "Band 6 (合格)",
        "action": "TA和CC优先拉分。词汇多样性(同一个意思用3种说法)。T2观点深度(举例具体化+解释充分)。复杂句成功率60%+。避免模板化表达。",
        "focus_4weeks": "第1周: 四维诊断→找出最低维。第2周: 最低维专项训练。第3周: 限时模写+逐句批改。第4周: 四维都≥6.0冲刺。"
    },
    "7.0": {
        "band_label": "Band 7 (良好)",
        "action": "论证深度提升(counter-argument+nuance)。词汇精确度(less common items)。句式灵活性(倒装/虚拟/分词)。IELTS风格内化。",
        "focus_4weeks": "全真模考+逐句精批+考官范文仿写。"
    }
}

WRITING_ROADMAPS = {
    "3.0→4.0": {
        "duration": "2-4个月", "goal": "简单句正确率<30%→60%+ | T2≥120词 | 能有意识地使用时态",
        "phase_4weeks": [
            {"周": 1, "焦点": "写出正确简单句", "任务": "简单句×10句/天(自我介绍/家乡/昨天)。语法: 一般现在时为主。不碰复杂句。", "检验": "每天不间断完成10句"},
            {"周": 2, "焦点": "引入过去时", "任务": "简单句×10句/天: 混合现在时+过去时。写完检查时态一致性。", "检验": "10句中≥7句时态正确"},
            {"周": 3, "焦点": "段落概念建立", "任务": "T2写4段式结构(每段3-5句)。先写满250词，不管质量。", "检验": "T2≥250词+4段完整"},
            {"周": 4, "焦点": "第一次综合检验", "任务": "T2不限时写作(目标120词+)。重点检查: 简单句正确率。", "检验": "T2≥120词 + 60%句子语法正确"}
        ]
    },
    "4.0→5.0": {
        "duration": "2-4个月", "goal": "T1≥150词/T2≥200词 | 4段式结构稳定 | 衔接词基本使用",
        "phase_4weeks": [
            {"周": 1, "焦点": "T1结构定型", "任务": "T1背4段式模板(引入→概览→细节1→细节2)。线图×1篇+柱图×1篇(对照范文批改)。", "检验": "T1结构完整+有概览"},
            {"周": 2, "焦点": "T2结构+字数", "任务": "T2 4段式结构(引入→Body1→Body2→结论)。先写满250词。PEEL论证(P+E至少两步)。", "检验": "T2≥250词+4段结构完整"},
            {"周": 3, "焦点": "衔接词入门", "任务": "淘汰firstly/secondly→用Furthermore/In contrast/As a result。T1+T2各一篇含3种以上衔接。", "检验": "衔接词≥3种+使用正确"},
            {"周": 4, "焦点": "T1+T2限时模写", "任务": "T1 20min+T2 40min限时模写。重点检查: 字数+结构+衔接。", "检验": "T1≥140词/T2≥220词 +结构完整"}
        ]
    },
    "5.0→6.0": {
        "duration": "2-6个月 ⚠️高原突破",
        "goal": "固化错误降50% | 复杂句成功率30%→60%+ | 衔接词自然多样",
        "phase_4weeks": [
            {"周": 1, "焦点": "错误模式诊断", "任务": "收集过去3篇T2作文→逐句标记语法错误→统计Top3错误类型→制作'我的错误清单'。", "检验": "完成错误类型统计表"},
            {"周": 2, "焦点": "Top3错误歼灭+衔接词升级", "任务": "只盯Top3错误写作×3篇(不限时，写完只检查这3类)。衔接词升级练习(淘汰firstly/secondly)。", "检验": "Top3错误频率下降30%"},
            {"周": 3, "焦点": "复杂句成功率", "任务": "一稿二写法×3次(第一稿用舒服方式→第二稿挑5个简单句合并为复杂句)。目标: 每篇3-5个正确复杂句。", "检验": "复杂句成功率≥40%"},
            {"周": 4, "焦点": "综合检验", "任务": "T1+T2限时模写60min。重点: Top3错误显著减少? 衔接词≥5种? 复杂句≥3个正确?", "检验": "Top3错误降≥40% | 衔接词≥5种 | 复杂句≥3个正确"}
        ]
    },
    "6.0→7.0": {
        "duration": "2-4个月", "goal": "论证深度+词汇多样性+句式灵活性 | 四维都≥6.0",
        "phase_4weeks": [
            {"周": 1, "焦点": "四维精确诊断", "任务": "T1+T2各写1篇→四维诊断(TA/CC/LR/GRA)→找出最低维。", "检验": "完成四维诊断报告"},
            {"周": 2, "焦点": "最低维专项突破", "任务": "针对最低维×4天专项。TA→审题/CC→段落结构/LR→词汇升级/GRA→复杂句。", "检验": "最低维分数提升0.5+"},
            {"周": 3, "焦点": "限时模写+逐句批改", "任务": "T1+T2限时60min×2次。逐句批改: 复杂句/词汇重复/衔接。", "检验": "四维都≥5.5"},
            {"周": 4, "焦点": "冲刺6.0+", "任务": "T1+T2限时模写→四维都≥6.0? 重点: 论证深度+词汇多样性。", "检验": "四维都≥6.0"}
        ]
    }
}


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
