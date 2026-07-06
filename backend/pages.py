"""
用户前端页面 — Landing / Dashboard（纯 HTML，FastAPI 服务端渲染）

部署在 FastAPI 同一进程，无需额外前端服务。
如需微信小程序，可基于此 API 层重新实现。
"""

import sqlite3
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["pages"])
_DB_PATH = Path(__file__).parent / "data" / "saas.db"

LANDING_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>IELTS Grader - AI雅思写作批改</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, 'PingFang SC', sans-serif; color: #333; }
.hero { text-align: center; padding: 80px 20px 60px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
.hero h1 { font-size: 2.5em; margin-bottom: 16px; }
.hero p { font-size: 1.2em; opacity: 0.9; max-width: 600px; margin: 0 auto 32px; }
.hero .btn { display: inline-block; background: white; color: #667eea; padding: 14px 40px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 1.1em; margin: 0 8px; }
.hero .btn.outline { background: transparent; color: white; border: 2px solid white; }
.features { max-width: 1000px; margin: 60px auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 24px; padding: 0 20px; }
.feature { text-align: center; padding: 24px; }
.feature .icon { font-size: 2.5em; margin-bottom: 12px; }
.feature h3 { margin-bottom: 8px; }
.feature p { color: #666; font-size: 0.95em; line-height: 1.5; }
.how { background: #f8f9fa; padding: 60px 20px; text-align: center; }
.how h2 { margin-bottom: 32px; }
.steps { max-width: 700px; margin: 0 auto; display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }
.step { background: white; border-radius: 12px; padding: 24px; flex: 1; min-width: 180px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.step .num { background: #667eea; color: white; width: 32px; height: 32px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 12px; font-weight: bold; }
.footer { text-align: center; padding: 32px; color: #999; font-size: 0.85em; }
</style></head>
<body>
<div class="hero">
  <h1>📝 IELTS Grader</h1>
  <p>AI 雅思写作批改 · 四维评分 · 分段画像 · 提分路线图</p>
  <div>
    <a class="btn" href="/pricing">开始使用 →</a>
    <a class="btn outline" href="/pricing">查看定价</a>
  </div>
</div>
<div class="features">
  <div class="feature"><div class="icon">🎯</div><h3>四维评分</h3><p>TA/CC/LR/GRA 四维度精确评分，每维度附评分理由</p></div>
  <div class="feature"><div class="icon">📊</div><h3>分段画像</h3><p>Band 3.0~7.0 精确画像，定位你的真实水平</p></div>
  <div class="feature"><div class="icon">🗺️</div><h3>提分路线图</h3><p>从当前 Band 到下一级别，分周执行计划</p></div>
  <div class="feature"><div class="icon">❌</div><h3>语法定位</h3><p>Top3 错误类型 + 示例，精准打击弱项</p></div>
</div>
<div class="how">
  <h2>三步开始</h2>
  <div class="steps">
    <div class="step"><div class="num">1</div><h3>选方案</h3><p>免费试用或付费订阅</p></div>
    <div class="step"><div class="num">2</div><h3>付款</h3><p>微信/支付宝扫码支付</p></div>
    <div class="step"><div class="num">3</div><h3>评分</h3><p>粘贴作文 → AI 秒出评分报告</p></div>
  </div>
  <p style="margin-top:24px;"><a href="/pricing" style="color:#667eea;font-weight:600;">立即开始 →</a></p>
</div>
<div class="footer">
  <p>支持微信/支付宝付款 · 有问题请联系作者</p>
</div>
</body></html>"""


# ── Dashboard ──

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>控制台 - IELTS Grader</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; }
.nav { background: white; padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.nav h2 { font-size: 1.1em; }
.nav a { color: #667eea; text-decoration: none; font-size: 0.9em; }
.container { max-width: 800px; margin: 24px auto; padding: 0 16px; }
.card { background: white; border-radius: 12px; padding: 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.card h3 { font-size: 1em; color: #666; margin-bottom: 12px; }
.key-box { display: flex; align-items: center; gap: 8px; background: #f8f9fa; padding: 12px 16px; border-radius: 8px; font-family: monospace; font-size: 0.9em; word-break: break-all; }
.key-box button { background: #667eea; color: white; border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; white-space: nowrap; }
.key-box button:hover { background: #5a6fd6; }
.credits { font-size: 2em; font-weight: bold; color: #27ae60; }
.credits span { font-size: 0.4em; color: #999; }
textarea { width: 100%; min-height: 200px; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 0.95em; font-family: inherit; resize: vertical; }
.btn { background: #667eea; color: white; border: none; padding: 10px 24px; border-radius: 8px; cursor: pointer; font-size: 1em; margin-top: 8px; }
.btn:hover { background: #5a6fd6; }
.btn.green { background: #27ae60; }
.result { margin-top: 12px; padding: 12px; border-radius: 8px; background: #f8f9fa; white-space: pre-wrap; font-size: 0.9em; display: none; }
.result.show { display: block; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 8px 6px; font-size: 0.85em; border-bottom: 1px solid #eee; }
th { color: #666; font-weight: 500; }
.upgrade { display: inline-block; background: #27ae60; color: white; text-decoration: none; padding: 8px 20px; border-radius: 6px; font-size: 0.9em; }
.error { color: #e74c3c; font-size: 0.85em; margin-top: 4px; }
</style></head>
<body>
<div class="nav">
  <h2>📝 IELTS Grader</h2>
  <div>
    <a href="/pricing">定价</a>
    <a href="/docs" style="margin-left:16px;">API文档</a>
  </div>
</div>
<div class="container">
  <!-- Key & Credits -->
  <div class="card">
    <h3>🔑 你的 API Key</h3>
    <div class="key-box">
      <span id="apiKey">加载中...</span>
      <button onclick="copyKey()">复制</button>
    </div>
    <p style="margin-top:8px;font-size:0.85em;color:#999;">在 HTTP Header 中传入: <code>Authorization: Bearer &lt;你的Key&gt;</code></p>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    <div class="card">
      <h3>📊 剩余额度</h3>
      <div class="credits" id="credits">-</div>
      <p style="color:#999;font-size:0.85em;">总计 <span id="totalCredits">-</span> 次</p>
      <a href="/pricing" class="upgrade" style="margin-top:12px;display:inline-block;">续费/升级 →</a>
    </div>
    <div class="card">
      <h3>📋 方案</h3>
      <p style="font-size:1.2em;" id="planName">-</p>
      <p style="color:#999;font-size:0.85em;">已用 <span id="usedCredits">-</span> 次评分</p>
    </div>
  </div>

  <!-- 在线测试评分 -->
  <div class="card">
    <h3>✏️ 在线测试评分</h3>
    <p style="color:#999;font-size:0.85em;margin-bottom:8px;">粘贴雅思作文，立即查看评分报告</p>
    <textarea id="essayInput" placeholder="在此粘贴雅思作文..."></textarea>
    <button class="btn" onclick="testGrade()">🚀 开始评分</button>
    <div id="gradeResult" class="result"></div>
  </div>

  <!-- 评分历史 -->
  <div class="card">
    <h3>📜 评分历史</h3>
    <table><thead><tr><th>时间</th><th>字数</th><th>结果</th></tr></thead><tbody id="historyBody"><tr><td colspan="3" style="text-align:center;color:#999;padding:16px;">加载中...</td></tr></tbody></table>
  </div>
</div>

<script>
const KEY_STORAGE = 'ielts_grader_key';

// 初始化：从 URL 参数或 localStorage 读取 Key
const params = new URLSearchParams(window.location.search);
const urlKey = params.get('key');
if (urlKey) {
  localStorage.setItem(KEY_STORAGE, urlKey);
  window.history.replaceState({}, '', '/dashboard');
}

function getKey() {
  return localStorage.getItem(KEY_STORAGE) || '';
}

function setKey(key) {
  localStorage.setItem(KEY_STORAGE, key);
}

// 页面加载
async function loadDashboard() {
  const key = getKey();
  if (!key) {
    document.getElementById('apiKey').textContent = '未设置 Key';
    document.getElementById('credits').textContent = '0';
    return;
  }
  document.getElementById('apiKey').textContent = key;
  setKey(key);
  await loadMe();
  await loadHistory();
}

// 复制 Key
function copyKey() {
  const key = getKey();
  if (!key) return;
  navigator.clipboard.writeText(key).then(() => {
    const btn = document.querySelector('.key-box button');
    btn.textContent = '✅ 已复制';
    setTimeout(() => btn.textContent = '复制', 2000);
  });
}

// 查额度
async function loadMe() {
  const key = getKey();
  try {
    const resp = await fetch('/v1/me', {
      headers: { 'Authorization': 'Bearer ' + key }
    });
    if (!resp.ok) throw new Error('Key 无效');
    const data = await resp.json();
    document.getElementById('credits').textContent = data.credits_remaining;
    document.getElementById('totalCredits').textContent = data.credits_total;
    document.getElementById('usedCredits').textContent = data.credits_total - data.credits_remaining;
    document.getElementById('planName').textContent = data.plan;
  } catch(e) {
    document.getElementById('credits').textContent = 'Key 无效或过期';
    document.querySelector('.error-msg').textContent = e.message;
  }
}

// 测试评分
async function testGrade() {
  const key = getKey();
  const essay = document.getElementById('essayInput').value;
  if (!key) { alert('请先获取 API Key（在下方选择方案付款后获得）'); return; }
  if (essay.trim().length < 20) { alert('作文太短（至少20字）'); return; }

  const result = document.getElementById('gradeResult');
  result.className = 'result show';
  result.textContent = '⏳ 评分中...';
  const btn = document.querySelector('#gradeResult + .btn');
  btn.disabled = true;
  btn.textContent = '⏳ 评分中...';

  try {
    const resp = await fetch('/v1/grade', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' },
      body: JSON.stringify({ essay, task_type: 'T2', format: 'json' }),
    });
    const data = await resp.json();
    if (data.success) {
      const dims = Object.entries(data.dimensions || {})
        .map(([k,v]) => `${k}: Band ${v.band} — ${(v.rationale || '').slice(0,40)}`)
        .join('\\n');
      result.innerHTML = '📊 Overall: <strong>Band ' + data.overall_band + '</strong>\\n' +
        '剩余额度: ' + data.credits_remaining + ' 次\\n\\n' +
        '四维评分:\\n' + dims + '\\n\\n' +
        '<a href="/v1/grade?format=html" style="color:#667eea;">查看完整 HTML 报告 →</a>';
      loadMe();
    } else {
      result.textContent = '❌ ' + (data.error || '评分失败');
    }
  } catch(e) {
    result.textContent = '❌ 网络错误: ' + e.message;
  }

  btn.disabled = false;
  btn.textContent = '🚀 开始评分';
}

// 评分历史
async function loadHistory() {
  // 简化版：显示最近调用记录（需要额外 API，暂时显示提示）
  document.getElementById('historyBody').innerHTML =
    '<tr><td colspan="3" style="text-align:center;color:#999;padding:16px;">评分历史功能开发中</td></tr>';
}

loadDashboard();
</script>
</body></html>"""


@router.get("/landing", response_class=HTMLResponse)
def landing():
    return LANDING_HTML


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML
