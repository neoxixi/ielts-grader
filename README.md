# IELTS Grader — 雅思写作 AI 批改系统

> 🎯 输入雅思作文 → 四维 AI 评分 → 分段画像 → 提分建议 → 4周路线图

## ✨ 功能

- **四维评分**: TA/CC/LR/GRA 每维度 Band + 评分理由
- **分段画像**: Band 3.0~7.0 精确画像与核心优先级
- **语法定位**: Top3 错误类型 + 示例
- **模板检测**: 识别模板化表达
- **交叉验证**: LLM 评分 + 启发式评分，差异≥1.0 Band 自动重评取平均
- **提分建议**: 融合 AI 建议 + 专家知识库
- **4周路线图**: Band 级别→下一级别 分周执行计划
- **T1+T2 综合**: 按 IELTS 规则 (T1×1/3 + T2×2/3) 计算写作总分

## 📦 安装

```bash
# 从源码安装
git clone https://github.com/neoqi/ielts-grader
cd ielts-grader
pip install -e .

# 安装 Web UI 支持（可选）
pip install -e ".[web]"

# 安装全部（含 weasyprint PDF）
pip install -e ".[all]"
```

### 依赖

- Python ≥ 3.10
- `openai` SDK（调用 DeepSeek API）
- API Key 自动从 `~/.claude/settings.json` 读取

## 🚀 使用

### 命令行

```bash
# 使用内置示例作文（默认 Band 5 典型高原期）
ielts-grader

# 自定义作文
ielts-grader --text "Your essay content here..." --task T2

# 从文件读取
ielts-grader --file essay.txt --html

# 管道输入
echo "Your essay..." | ielts-grader

# 交互模式
ielts-grader --interactive

# 列出内置示例
ielts-grader --list-samples

# 指定示例 + HTML 报告
ielts-grader --sample "Band 6 (合格)" --html

# 输出 JSON
ielts-grader --text "..." --output result.json
```

### Python 调用

```python
from ielts_grader import grade_essay, build_enriched_report, print_report

# 评分
llm_result = grade_essay("Your essay...", task_type="T2")

# 融合专家知识库
report = build_enriched_report(llm_result, "Your essay...", "T2")

# 打印报告
print_report(report)

# 生成 HTML
from ielts_grader import render_html
html = render_html(report, "report.html")
```

### Web UI

```bash
ielts-grader-webui
# 或
python3 -m ielts_grader.cli webui

# 然后打开 http://localhost:7860
```

## 🧠 评分维度

| 维度 | 全称 | 评分要点 |
|------|------|---------|
| **TA** | Task Achievement/Response | 任务完成度、论点充分性、数据描述准确性 |
| **CC** | Coherence and Cohesion | 段落结构、衔接词自然度、逻辑连贯性 |
| **LR** | Lexical Resource | 词汇多样性、同义替换、搭配准确性 |
| **GRA** | Grammatical Range and Accuracy | 句式多样性、语法错误频率、复杂句成功率 |

## 🔧 配置

评分默认使用 DeepSeek API（OpenAI 兼容模式）。API Key 优先级：

1. `~/.claude/settings.json` → `env.ANTHROPIC_API_KEY`
2. 环境变量 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`

模型名优先级：

1. 环境变量 `LLM_MODEL`
2. `~/.claude/settings.json` → `model`
3. 默认 `deepseek-chat`

```bash
# 使用 GPT-4
LLM_MODEL=gpt-4 OPENAI_BASE_URL=https://api.openai.com ielts-grader --text "..."

# 使用 Claude
LLM_MODEL=claude-sonnet-5-20251001 ANTHROPIC_BASE_URL=https://api.anthropic.com ielts-grader --text "..."
```

## 🗺️ 路线规划

- [x] CLI 工具（`ielts-grader`）
- [x] Gradio Web UI（`ielts-grader-webui`）
- [x] 四维评分 + 分段画像 + 4周路线图
- [x] 交叉验证防误评
- [ ] WeasyPrint PDF 导出
- [ ] 多作文历史追踪
- [ ] 学生画像（长期弱项分析）
- [ ] SaaS API 模式

## 📄 License

MIT
