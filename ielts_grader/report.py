"""
报告渲染模块 — 控制台 / HTML / JSON
"""

import json
from datetime import datetime
from pathlib import Path


def print_report(result: dict, essay_text: str = ""):
    """在控制台打印评分报告"""
    enriched = result.get("enriched_recommendations", {})

    print("\n" + "=" * 60)
    print("📝  IELTS 写作 AI 批改报告")
    print("=" * 60)
    print(f"\n📊 总评分: Band {result['overall_band']}")

    bp = result.get("band_profile", {})
    if bp:
        print(f"   分段: {bp.get('band_key', '')} — {bp.get('label', '')}")
        print(f"   概述: {bp.get('overall', '')}")
        print(f"   核心优先级: {bp.get('priority', '')}")
    print(f"\n   Task: {result['task_type']}  |  字数: {result['word_count']}")

    print(f"\n┌─────┬───────┬────────────────────────────────────────────┐")
    print(f"│ 维度 │ Band  │ 评分理由                                    │")
    print(f"├─────┼───────┼────────────────────────────────────────────┤")
    for dk, dl in [("TA", "TA"), ("CC", "CC"), ("LR", "LR"), ("GRA", "GRA")]:
        dim = result.get("dimensions", {}).get(dk, {})
        if dim:
            print(f"│ {dl:<4}│ {dim.get('band', '?'):<6.1f}│ {dim.get('rationale', '')[:45]:<45}│")
    print(f"└─────┴───────┴────────────────────────────────────────────┘")

    if enriched.get("strengths"):
        print(f"\n✅ 写作优势:")
        for s in enriched["strengths"][:3]:
            print(f"   • {s}")
    if enriched.get("weaknesses"):
        print(f"\n⚠️  主要问题:")
        for w in enriched["weaknesses"][:3]:
            print(f"   • {w}")
    if enriched.get("actionable_tips"):
        print(f"\n🎯 提分建议:")
        for i, tip in enumerate(enriched["actionable_tips"][:6], 1):
            print(f"   {i}. {tip}")

    error_analysis = enriched.get("error_analysis", {})
    if error_analysis.get("grammar_top3"):
        print(f"\n❌ 语法错误 Top3:")
        for err in error_analysis["grammar_top3"]:
            examples = ", ".join(err.get("examples", [])[:2])
            print(f"   • {err.get('type', 'unknown')} (例如: {examples})")
    if error_analysis.get("connector_diversity"):
        print(f"\n🔗 衔接词多样性: {error_analysis['connector_diversity']}")
    if error_analysis.get("template_suspicion"):
        print(f"🚨 模板检测: {error_analysis['template_suspicion']}")

    ws = result.get("writing_strategy", {})
    if ws and ws.get("action"):
        print(f"\n📚 写作提升策略 ({ws.get('band_label', '')}):")
        print(f"   {ws['action'][:200]}")

    roadmap = result.get("roadmap")
    if roadmap and roadmap.get("phase_4weeks"):
        print(f"\n🗺️  4周提升路线图 ({roadmap.get('key', '')}):")
        print(f"   预计: {roadmap.get('duration', '')}  |  目标: {roadmap.get('goal', '')}")
        for phase in roadmap["phase_4weeks"]:
            print(f"\n   第{phase['周']}周 · {phase['焦点']}:")
            task_prev = phase['任务'][:80] + "..." if len(phase['任务']) > 80 else phase['任务']
            print(f"      {task_prev}")
            print(f"      ✅ 检验: {phase['检验']}")
    print()


def print_combined_report(combined: dict):
    """打印 T1+T2 综合报告"""
    sb = combined["score_breakdown"]
    bp = combined.get("band_profile", {})

    print("\n" + "=" * 60)
    print("📝  IELTS 写作综合报告（T1 + T2）")
    print("=" * 60)
    if combined.get("student"):
        print(f"  学生: {combined['student']}")
    print(f"\n📊 写作总分: Band {combined['overall_band']}")
    print(f"  T1 ({sb['task1']['band']}) × 1/3 + T2 ({sb['task2']['band']}) × 2/3")
    print(f"  = {sb['raw_total']} → Band {sb['rounded']}")
    print(f"\n  分段画像: {bp.get('label', '')}")
    print(f"  概述: {bp.get('overall', '')}")

    cross = combined.get("cross_task_analysis", {})
    if cross.get("priority_actions"):
        print(f"\n🎯 优先行动:")
        for i, tip in enumerate(cross["priority_actions"][:5], 1):
            print(f"   {i}. {tip}")
    print()


def render_html(result: dict, output_path: str = None) -> str:
    """生成 HTML 报告，返回 HTML 字符串。如果指定 output_path 则写入文件"""
    enriched = result.get("enriched_recommendations", {})
    tips_html = "".join(f"<li>{tip}</li>" for tip in enriched.get("actionable_tips", [])[:6])

    grammar_html = ""
    for err in enriched.get("error_analysis", {}).get("grammar_top3", []):
        examples = ", ".join(err.get("examples", [])[:2])
        grammar_html += f"<tr><td>{err.get('type', '')}</td><td>{examples}</td></tr>"

    dims = result.get("dimensions", {})
    dims_rows = "".join(
        f"<tr><td>{k}</td><td>{v.get('band', '?')}</td><td>{v.get('rationale', '')[:80]}</td></tr>"
        for k, v in dims.items()
    )

    bp = result.get("band_profile", {})
    roadmap = result.get("roadmap", {})
    phases_html = ""
    if roadmap and roadmap.get("phase_4weeks"):
        for phase in roadmap["phase_4weeks"]:
            phases_html += f"""
            <div class="phase">
                <h4>第{phase['周']}周 · {phase['焦点']}</h4>
                <p><strong>任务:</strong> {phase['任务']}</p>
                <p><strong>✅ 检验:</strong> {phase['检验']}</p>
            </div>"""

    strengths_html = "".join(f"<p>• {s}</p>" for s in enriched.get("strengths", [])[:3])
    weaknesses_html = "".join(
        f"<div class='weakness'>• {w}</div>" for w in enriched.get("weaknesses", [])[:3])

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>IELTS写作AI批改报告</title>
<style>
body {{ font-family: -apple-system, 'PingFang SC', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
.card {{ background: white; border-radius: 12px; padding: 20px; margin: 16px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
h1 {{ color: #2c3e50; }} h2 {{ color: #2980b9; font-size: 18px; }}
.band {{ font-size: 32px; font-weight: bold; color: #e74c3c; }}
table {{ width: 100%; border-collapse: collapse; }}
th,td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }}
th {{ background: #f8f9fa; }}
.phase {{ background: #eaf2f8; padding: 12px; margin: 8px 0; border-radius: 8px; }}
.weakness {{ background: #fdf2e9; padding: 10px; margin: 6px 0; border-left: 4px solid #e67e22; }}
.profile {{ background: #f4ecf7; padding: 12px; border-radius: 8px; }}
.vocab-note {{ background: #fef9e7; padding: 12px; border-left: 4px solid #f39c12; font-size: 14px; }}
@media print {{ body {{ background: white; }} .card {{ break-inside: avoid; }} }}
</style></head>
<body>
<h1>📝 IELTS 写作 AI 批改报告</h1>
<div class="card">
    <h2>📊 总评分</h2>
    <p><span class="band">Band {result['overall_band']}</span></p>
    <p>Task: {result['task_type']} | 字数: {result['word_count']}</p>
    <div class="profile">
        <strong>{bp.get('label', '')}</strong><br>
        {bp.get('overall', '')}<br>
        <strong>核心优先级:</strong> {bp.get('priority', '')}
    </div>
    <div class="vocab-note"><strong>📖 词汇表现:</strong><br>{bp.get('vocabulary_note', '')}</div>
</div>
<div class="card"><h2>四维评分</h2><table><tr><th>维度</th><th>Band</th><th>评分理由</th></tr>{dims_rows}</table></div>
<div class="card"><h2>🎯 提分建议</h2><ol>{tips_html}</ol></div>
{"" if not grammar_html else f"<div class='card'><h2>❌ 语法错误 Top3</h2><table><tr><th>类型</th><th>示例</th></tr>{grammar_html}</table></div>"}
<div class="card"><h2>✅ 写作优势</h2>{strengths_html}</div>
<div class="card"><h2>⚠️ 主要问题</h2>{weaknesses_html}</div>
{"" if not roadmap or not roadmap.get("phase_4weeks") else f'<div class="card"><h2>🗺️ 4周提升路线图</h2><p><strong>路线:</strong> {roadmap.get("key", "")} | <strong>预计:</strong> {roadmap.get("duration", "")}</p>{phases_html}</div>'}
<p style="color:#999;text-align:center;margin-top:30px;">由 IELTS Grader 生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</body></html>"""

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\n📄 HTML 报告已生成: {output_path}")

    return html
