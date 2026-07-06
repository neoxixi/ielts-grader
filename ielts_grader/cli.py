"""
CLI 入口 — `ielts-grader` 命令行工具

用法:
  ielts-grader --text "作文..." --task T2
  ielts-grader --file essay.txt --html
  ielts-grader --interactive
  echo "作文..." | ielts-grader
"""

import argparse, json, sys
from pathlib import Path


SAMPLE_ESSAYS = {
    "Band 5 (典型高原期)": (
        "Nowadays, technology is very important in our life. Many people use technology every day. "
        "I think technology has many advantages and disadvantages. "
        "First of all, technology make our life easier. For example, we can use internet to find information. "
        "Also, we can communicate with other people by using social media. "
        "Secondly, technology also have some disadvantages. "
        "Some people spend too much time on their phone. This is not good for their health. "
        "Moreover, technology can make people lazy because they don't need to think. "
        "In conclusion, I believe technology is a double-edged sword. "
        "We should use it wisely and not let it control our life. "
        "If we can balance between technology and real life, we will have a better future."
    ),
    "Band 6 (合格)": (
        "In recent years, the role of technology in education has become increasingly significant. "
        "While some argue that traditional teaching methods remain superior, I believe that "
        "integrating technology into classrooms offers more benefits. "
        "One of the primary advantages is that technology provides access to a vast amount of "
        "educational resources. Students can now access online libraries, educational videos, "
        "and interactive learning platforms, which were not available in the past. Furthermore, "
        "technology enables personalized learning experiences, allowing students to learn at "
        "their own pace and focus on areas where they need improvement. "
        "However, critics point out that excessive reliance on technology may reduce face-to-face "
        "interaction between teachers and students. They argue that this could negatively impact "
        "students' social skills development. Additionally, the digital divide means that not all "
        "students have equal access to technological resources, potentially widening educational "
        "inequalities. "
        "In my opinion, the key lies in finding the right balance. Technology should complement "
        "traditional teaching methods rather than replace them entirely. Teachers should be trained "
        "to effectively integrate technology into their lessons while maintaining meaningful "
        "interpersonal connections with their students."
    ),
    "Band 7 (良好)": (
        "The proliferation of digital technology has fundamentally transformed the landscape of "
        "higher education, raising pertinent questions about the optimal integration of these "
        "tools in academic settings. This essay will examine both the pedagogical benefits and "
        "potential drawbacks of technology-enhanced learning environments. "
        "On one hand, technological integration offers unprecedented opportunities for educational "
        "enhancement. Digital platforms facilitate access to a diverse range of scholarly resources, "
        "enabling students to engage with multiple perspectives on complex issues. Moreover, "
        "adaptive learning technologies can tailor educational content to individual learning styles, "
        "potentially increasing both engagement and knowledge retention. Research has demonstrated "
        "that blended learning approaches, combining online and face-to-face instruction, often yield "
        "superior outcomes compared to purely traditional methods. "
        "Nevertheless, the wholesale adoption of technology in education is not without its "
        "limitations. A significant concern is the potential erosion of critical thinking skills, "
        "as students may become overly reliant on readily available information rather than developing "
        "their analytical capabilities. Furthermore, the digital divide remains a pressing issue, "
        "as disparities in access to technology may exacerbate existing educational inequalities "
        "between socioeconomic groups. Additionally, the prevalence of digital distractions poses "
        "a substantial challenge to sustained concentration during learning activities. "
        "In conclusion, while technology undoubtedly offers powerful tools for enhancing education, "
        "its integration must be carefully managed. Educational institutions should adopt a "
        "balanced approach that harnesses technological benefits while preserving the invaluable "
        "human elements of teaching, such as mentorship, discussion, and critical dialogue."
    ),
}


def main():
    parser = argparse.ArgumentParser(
        description="IELTS 写作 AI 批改系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  ielts-grader                      # 使用内置示例作文评分
  ielts-grader --text "作文内容"     # 自定义作文
  ielts-grader --file essay.txt     # 从文件读取
  ielts-grader --interactive        # 交互模式
  ielts-grader --text "..." --html  # 生成 HTML 报告
  echo "作文" | ielts-grader        # 管道输入
  ielts-grader --list-samples       # 列出内置示例
        """
    )
    parser.add_argument("--text", help="作文文本")
    parser.add_argument("--file", help="从文件读取作文")
    parser.add_argument("--task", choices=["T1", "T2"], default="T2", help="Task 类型")
    parser.add_argument("--html", action="store_true", help="生成 HTML 报告")
    parser.add_argument("--output", help="输出 JSON 文件路径")
    parser.add_argument("--sample", help="使用内置示例作文 (--list-samples 查看)")
    parser.add_argument("--list-samples", action="store_true", help="列出内置示例")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    parser.add_argument("--prompt", help="v2 prompt YAML 路径 (默认自动查找)")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细日志")
    parser.add_argument("--version", action="store_true", help="显示版本号")
    parser.add_argument("--webui", action="store_true", help="启动 Gradio Web 界面")

    args = parser.parse_args()

    if args.webui:
        return webui()

    if args.version:
        from . import __version__
        print(f"ielts-grader v{__version__}")
        return

    if args.list_samples:
        print("内置示例作文:")
        for name in SAMPLE_ESSAYS:
            text = SAMPLE_ESSAYS[name]
            print(f"  {name} ({len(text.split())} 词)")
        return

    # ── 读取作文 ──
    essay = None
    if args.text:
        essay = args.text
    elif args.file:
        try:
            with open(args.file) as f:
                essay = f.read()
        except FileNotFoundError:
            print(f"❌ 文件不存在: {args.file}")
            sys.exit(1)
    elif args.sample:
        if args.sample in SAMPLE_ESSAYS:
            essay = SAMPLE_ESSAYS[args.sample]
            print(f"📝 使用内置示例: {args.sample}")
        else:
            print(f"❌ 未知示例: {args.sample}")
            print(f"   可用: {', '.join(SAMPLE_ESSAYS.keys())}")
            sys.exit(1)
    elif not sys.stdin.isatty():
        essay = sys.stdin.read().strip()
    else:
        # 默认使用 Band 5 示例
        essay = list(SAMPLE_ESSAYS.values())[0]
        print(f"📝 使用默认示例作文 (Band 5 典型高原期，{len(essay.split())} 词)")
        print(f"   用 --text 或 --file 传入自己的作文")

    if not essay or not essay.strip():
        print("❌ 未提供作文")
        sys.exit(1)

    # ── 执行评分 ──
    from .grader import grade_essay
    from .core import build_enriched_report
    from .report import print_report, render_html

    if args.verbose:
        print(f"\n🔍 正在评分 (Task {args.task}, {len(essay.split())} 词)...")

    prompt_path = args.prompt
    if not prompt_path:
        # 自动查找 v2 prompt
        candidates = [
            Path(__file__).resolve().parent / "prompts" / "ielts_writing_v2.yaml",
            Path("/home/neoqi/yangneng/evaluation/prompts/ielts_writing_v2.yaml"),
        ]
        for p in candidates:
            if p.exists():
                prompt_path = str(p)
                break

    llm_result = grade_essay(essay, args.task, prompt_path=prompt_path, verbose=args.verbose)
    enriched = build_enriched_report(llm_result, essay, args.task)

    # ── 输出 ──
    print_report(enriched, essay)

    if args.html or args.output:
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        if args.html:
            out_dir = Path("output")
            out_dir.mkdir(exist_ok=True)
            html_path = out_dir / "report.html"
            render_html(enriched, str(html_path))

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(enriched, f, ensure_ascii=False, indent=2)
            print(f"\n📄 JSON 已保存: {out_path}")
    else:
        json_output = Path("output") / "latest_report.json"
        json_output.parent.mkdir(exist_ok=True)
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)


def webui():
    """启动 Gradio Web 界面 (pip install ielts-grader[web])"""
    try:
        import gradio as gr
    except ImportError:
        print("❌ 需要安装 gradio: pip install ielts-grader[web]")
        sys.exit(1)

    from .grader import grade_essay, _has_api_key
    from .core import build_enriched_report
    from .report import render_html

    has_key = _has_api_key()
    if not has_key:
        print("⚠️  未检测到 API Key，WebUI 将使用离线评分（精度有限）")

    def grade(essay, task_type, use_api):
        if not essay or len(essay.strip()) < 20:
            return "请输入完整的作文（至少20字）", "", "", ""
        if use_api:
            llm_result = grade_essay(essay, task_type, verbose=False)
        else:
            from .core import heuristic_score
            llm_result = heuristic_score(essay, task_type)
        enriched = build_enriched_report(llm_result, essay, task_type)
        html_report = render_html(enriched)

        dims = enriched.get("dimensions", {})
        dims_text = "\n".join(
            f"{k}: Band {v.get('band', '?')} — {v.get('rationale', '')[:50]}"
            for k, v in dims.items()
        )
        tips = "\n".join(
            f"{i}. {t}" for i, t in enumerate(
                enriched.get("enriched_recommendations", {}).get("actionable_tips", [])[:5], 1))

        return (
            f"## Overall: Band {enriched['overall_band']}\n\n"
            f"{enriched.get('band_profile', {}).get('label', '')}\n\n"
            f"**字数**: {enriched['word_count']}",
            dims_text,
            tips,
            html_report,
        )

    css = """
    .gradio-container { max-width: 900px; margin: auto; }
    .report-iframe { width: 100%; height: 600px; border: none; }
    """
    sample_options = list(SAMPLE_ESSAYS.keys())

    with gr.Blocks(title="IELTS 写作 AI 批改") as demo:
        gr.Markdown("# 📝 IELTS 写作 AI 批改系统")
        if not has_key:
            gr.Markdown("> ⚠️ 未检测到 API Key，将使用**离线启发式评分**（精度有限）。\n> 设置方法: `export ANTHROPIC_API_KEY=your_key`")
        gr.Markdown("输入作文 → AI 四维评分 → 分段画像 → 提分建议 → 4周路线图")

        with gr.Row():
            with gr.Column(scale=2):
                essay_input = gr.Textbox(
                    label="作文内容", lines=12, placeholder="在此粘贴或输入雅思作文...",
                    value=list(SAMPLE_ESSAYS.values())[0])
            with gr.Column(scale=1):
                task_type = gr.Radio(["T1 (图表)", "T2 (议论文)"], label="Task 类型", value="T2 (议论文)")
                use_api = gr.Checkbox(label="使用 AI 评分 (需 API Key)", value=True)
                sample_dropdown = gr.Dropdown(
                    choices=sample_options, label="示例作文", value=sample_options[0])
                submit_btn = gr.Button("开始评分 🚀", variant="primary", size="lg")

        with gr.Row():
            with gr.Column():
                overall = gr.Markdown(label="总评分")
            with gr.Column():
                dims_out = gr.Textbox(label="四维评分", lines=4)
            with gr.Column():
                tips_out = gr.Textbox(label="提分建议", lines=4)

        report_html = gr.HTML(label="完整报告")

        def load_sample(name):
            return SAMPLE_ESSAYS[name]

        sample_dropdown.change(load_sample, sample_dropdown, essay_input)
        submit_btn.click(
            lambda e, t, a: grade(e, t.replace(" (图表)", "").replace(" (议论文)", ""), a),
            [essay_input, task_type, use_api],
            [overall, dims_out, tips_out, report_html])

    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, css=css, theme=gr.themes.Soft())


if __name__ == "__main__":
    main()
