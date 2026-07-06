# IELTS Grader — 雅思写作 AI 批改系统

> 🎯 输入雅思作文 → 四维 AI 评分 → 分段画像 → 提分建议 → 4周路线图

> **⚠️ 许可证 & 知识产权**
> - 本项目基于 **AGPL-3.0** 发布
> - 完整专家知识库（Band画像/策略/路线图）和高级评分 Prompt **不在此公开仓库中**
> - 公开版仅含 Band 5 演示数据，完整版需通过商业授权获取
> - **商业使用**: 如需闭源集成、白标部署或 SaaS 商业授权，请联系我们
> - **隐私声明**: 你的 API Key 仅在本地使用，代码不会向外发送非评分请求

### 🏗️ 架构说明

```
公开仓库 (GitHub)                 私有存储 (~/.ielts-grader-private/)
├── CLI + WebUI 框架               ├── 完整 Band 画像 (Band 3-7)
├── 启发式评分引擎                  ├── 完整写作策略 (5个Band级别)
├── LLM API 调用层                 ├── 完整4周路线图 (4个阶段)
├── Lite 知识库 (仅 Band 5)        └── v2 高级评分 Prompt
└── 基础评分 Prompt (内置)
         ↓                                  ↓
  公开版可正常评分                   完整版才有专家知识库增强
  (LLM评分不受影响)                  (分段画像+策略+路线图)
```

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

评分默认使用 DeepSeek API（OpenAI 兼容模式）。需要先设置 API Key。

### API Key 设置（二选一）

**方式一：环境变量（推荐开源用户）**
```bash
export ANTHROPIC_API_KEY="sk-your-key-here"
export OPENAI_BASE_URL="https://api.deepseek.com"  # 默认已指向 DeepSeek
```

**方式二：Claude Code 配置文件（仅供 Claude Code 用户）**
`~/.claude/settings.json` 中的 `env.ANTHROPIC_API_KEY`

> **安全说明**: API Key 仅在本地使用，代码仅发送评分请求到配置的 API 地址。
> 你可以通过 `OPENAI_BASE_URL` 切换到任意 OpenAI 兼容服务（如 GPT-4、Claude 等）。

### 模型选择

```bash
# DeepSeek（默认，性价比最高）
export LLM_MODEL="deepseek-chat"

# GPT-4（更贵但公认更准）
export LLM_MODEL="gpt-4o"
export OPENAI_BASE_URL="https://api.openai.com"

# Claude
export LLM_MODEL="claude-sonnet-5-20251001"
export OPENAI_BASE_URL="https://api.anthropic.com"
```

### 优先级

API Key: 环境变量 > `~/.claude/settings.json`
模型名: 环境变量 `LLM_MODEL` > `~/.claude/settings.json` > 默认 `deepseek-chat`

```bash
# 使用 GPT-4
LLM_MODEL=gpt-4 OPENAI_BASE_URL=https://api.openai.com ielts-grader --text "..."

# 使用 Claude
LLM_MODEL=claude-sonnet-5-20251001 ANTHROPIC_BASE_URL=https://api.anthropic.com ielts-grader --text "..."
```

## 🌐 SaaS API (Backend)

本项目包含完整的 SaaS 后端，支持 API Key 认证 + 额度管理 + 支付集成。

### 快速启动后端

```bash
cd ielts-grader

# 设置管理员 Key
export ADMIN_API_KEY="your-admin-key"

# 启动服务
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/pricing` | 定价页面 |
| GET | `/v1/keys/free` | 免费领取 3 次试用 |
| GET | `/v1/me` | 查看剩余额度 |
| POST | `/v1/grade` | 作文评分 |
| POST | `/v1/keys` | (管理员) 创建 API Key |
| POST | `/v1/payments/checkout` | 创建购买链接 |
| GET | `/v1/payments/checkout-redirect/{plan}` | 定价页购买跳转 |
| POST | `/v1/payments/webhook` | Lemon Squeezy 支付回调 |

### API 使用示例

```bash
# 1. 获取免费 Key
KEY=$(curl -s http://localhost:8000/v1/keys/free | python3 -c "import sys,json;print(json.load(sys.stdin)['api_key'])")

# 2. 评分
curl -X POST http://localhost:8000/v1/grade \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"essay":"Your essay...","task_type":"T2","format":"json"}'
```

### 部署

```bash
# Docker
docker build -t ielts-grader -f backend/Dockerfile .
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=your-key \
  -e ADMIN_API_KEY=your-admin-key \
  -v ~/.ielts-grader-private:/root/.ielts-grader-private \
  ielts-grader
```

> **注意**: 生产部署需挂载 `~/.ielts-grader-private/` 以使用完整知识库

## 🗺️ 路线规划

- [x] CLI 工具（`ielts-grader`）
- [x] Gradio Web UI（`ielts-grader-webui`）
- [x] 四维评分 + 分段画像 + 4周路线图
- [x] 交叉验证防误评
- [x] SaaS API 后端（FastAPI + 认证 + 额度管理）
- [x] Lemon Squeezy 支付集成
- [x] Docker 部署
- [ ] WeasyPrint PDF 导出
- [ ] 多作文历史追踪
- [ ] 学生画像（长期弱项分析）

## 📄 License

**AGPL-3.0** © 2026 Neoqi (neoxixi)

本项目的专家知识库（包括但不限于 Band 画像、写作策略、4周路线图）和
评分 Prompt 受版权保护。任何修改后的网络服务版本必须开源其完整源码。

**商业授权**: 如需闭源集成、白标部署或 SaaS 商业使用，请联系我们。
未经授权的商业复制或转售将追究法律责任。

---

*Built with ❤️ for IELTS learners worldwide*
