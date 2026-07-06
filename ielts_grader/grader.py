"""
LLM API 调用模块 — DeepSeek / OpenAI / Anthropic 兼容
"""

import json, os, re
from pathlib import Path


def _get_api_key() -> str:
    """从 Claude Code 配置中读取 API Key"""
    settings_paths = [
        os.path.expanduser("~/.claude/settings.local.json"),
        os.path.expanduser("~/.claude/settings.json"),
    ]
    for sp in settings_paths:
        try:
            with open(sp) as f:
                cfg = json.load(f)
            key = cfg.get("env", {}).get("ANTHROPIC_API_KEY", "")
            if key:
                return key
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""


def _get_model() -> str:
    """从环境变量或 Claude Code 配置读取模型名"""
    model = os.environ.get("LLM_MODEL", "")
    if model:
        return model
    settings_paths = [
        os.path.expanduser("~/.claude/settings.local.json"),
        os.path.expanduser("~/.claude/settings.json"),
    ]
    for sp in settings_paths:
        try:
            with open(sp) as f:
                cfg = json.load(f)
            model = cfg.get("model", "") or cfg.get("env", {}).get("ANTHROPIC_MODEL", "")
            if model:
                return model
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return os.environ.get("LLM_MODEL", "deepseek-chat")


def _load_v2_prompt(task_type: str, prompt_path: str = None) -> str:
    """加载 v2 prompt（内含评分对照表 + 锚定范文）"""
    if prompt_path and Path(prompt_path).exists():
        try:
            import yaml
            with open(prompt_path) as f:
                cfg = yaml.safe_load(f)
            parts = [cfg.get("system_prompt_common", "")]
            if task_type == "T1":
                parts.append(cfg.get("task1_specific", ""))
            else:
                parts.append(cfg.get("task2_specific", ""))
            return "\n\n".join(parts)
        except Exception:
            pass

    # 内置 fallback prompt
    return f"""你是 IELTS 写作评分专家，拥有 10 年以上雅思写作教学和 IELTS 官方评分经验。
你必须严格遵循 IELTS Writing Band Descriptors 进行评分。

评分四维度:
- TA (Task Achievement/Response): 任务完成度
- CC (Coherence and Cohesion): 连贯与衔接
- LR (Lexical Resource): 词汇资源
- GRA (Grammatical Range and Accuracy): 语法范围与准确性

Band范围: 1.0-9.0，0.5 为增量。
{"T1评分: 数据描述准确、清晰概述、趋势对比、无个人观点。" if task_type == "T1" else "T2评分: 完整回应题目、清晰一致立场、充分具体论证、4-5段结构。"}

严格输出 JSON，不要包含任何其他文字。格式:
{{
  "task_type": "{task_type}",
  "word_count": int,
  "overall_band": float,
  "dimensions": {{
    "TA": {{"band": float, "rationale": "str(中文评分理由)", "strengths": ["str"], "weaknesses": ["str"]}},
    "CC": {{"band": float, "rationale": "str", "strengths": ["str"], "weaknesses": ["str"]}},
    "LR": {{"band": float, "rationale": "str", "strengths": ["str"], "weaknesses": ["str"]}},
    "GRA": {{"band": float, "rationale": "str", "strengths": ["str"], "weaknesses": ["str"]}}
  }},
  "summary": {{
    "estimated_band": float,
    "strengths": ["str"],
    "weaknesses": ["str"],
    "actionable_tips": ["str(至少3条具体可执行的提分建议)"],
    "error_analysis": {{
      "grammar_top3": [{{"type": "str", "examples": ["str"]}}],
      "connector_diversity": "str",
      "template_suspicion": "str"
    }}
  }}
}}"""


def grade_essay(essay: str, task_type: str = "T2",
                api_key: str = None, model: str = None,
                base_url: str = None, prompt_path: str = None,
                verbose: bool = False) -> dict:
    """
    调用 LLM API 评分雅思作文。

    参数:
        essay: 作文文本
        task_type: T1(图表) / T2(议论文)
        api_key: API Key (默认从 settings.json 读取)
        model: 模型名 (默认 deepseek-chat)
        base_url: API 地址 (默认 https://api.deepseek.com)
        prompt_path: v2 prompt yaml 路径
        verbose: 打印日志
    """
    from openai import OpenAI

    api_key = api_key or _get_api_key()
    model = model or _get_model()
    base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        if verbose:
            print("⚠️  未找到 API Key，使用启发式评分")
        from .core import heuristic_score
        return heuristic_score(essay, task_type)

    system_prompt = _load_v2_prompt(task_type, prompt_path)
    user_prompt = f"""请对以下 IELTS 写作 Task {task_type} 作文进行评分。

作文内容:
---
{essay}
---

请按要求的 JSON 格式输出评分结果。"""

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or ""
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            content = json_match.group(1).strip()
        result = json.loads(content)

        if "dimensions" not in result:
            raise ValueError("响应缺少 dimensions 字段")
        if "overall_band" not in result:
            result["overall_band"] = result.get("summary", {}).get("estimated_band", 5.0)
        if "word_count" not in result:
            result["word_count"] = len(essay.split())

        # 交叉验证: LLM vs 启发式
        from .core import heuristic_score
        heuristic = heuristic_score(essay, task_type)
        h_band = heuristic["overall_band"]
        l_band = result.get("overall_band", 5.0)
        diff = abs(h_band - l_band)
        if diff >= 1.0:
            if verbose:
                print(f"  ⚠️  LLM ({l_band}) vs 启发式 ({h_band}) 差异 {diff:.1f} Band，正在重评...")
            response2 = client.chat.completions.create(
                model=model, temperature=0, max_tokens=4096,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content2 = response2.choices[0].message.content or ""
            json_match2 = re.search(r'```(?:json)?\s*([\s\S]*?)```', content2)
            if json_match2:
                content2 = json_match2.group(1).strip()
            result2 = json.loads(content2)
            if "dimensions" in result2 and "overall_band" in result2:
                for dk in ["TA", "CC", "LR", "GRA"]:
                    d1 = result.get("dimensions", {}).get(dk, {}).get("band")
                    d2 = result2.get("dimensions", {}).get(dk, {}).get("band")
                    if d1 is not None and d2 is not None:
                        result["dimensions"][dk]["band"] = round((d1 + d2) / 2 * 2) / 2
                avg = round((result["overall_band"] + result2["overall_band"]) / 2 * 2) / 2
                result["overall_band"] = avg
                if verbose:
                    print(f"  ✅ 重评完成，取平均: Overall={avg}")

        return result

    except json.JSONDecodeError as e:
        if verbose:
            print(f"⚠️  JSON 解析失败: {e}")
        from .core import heuristic_score
        return heuristic_score(essay, task_type)
    except Exception as e:
        if verbose:
            print(f"⚠️  API 调用失败: {e}，回退到启发式评分")
        from .core import heuristic_score
        return heuristic_score(essay, task_type)
