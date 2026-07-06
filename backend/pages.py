"""
用户前端页面 — Landing / Dashboard / 领码 / 管理后台
"""

import sqlite3, secrets, string
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["pages"])
_DB_PATH = Path(__file__).parent / "data" / "saas.db"

# ── 定价方案（复用） ──
PLANS = {
    "free": {"name": "免费试用", "credits": 3, "price_cny": 0},
    "starter": {"name": "基础版", "credits": 30, "price_cny": 19.9},
    "pro": {"name": "专业版", "credits": 100, "price_cny": 59.9},
    "unlimited": {"name": "无限版", "credits": 9999, "price_cny": 199},
}


def _get_db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_tables():
    """确保激活码表存在"""
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activation_codes (
            code TEXT PRIMARY KEY,
            plan TEXT NOT NULL,
            credits INTEGER NOT NULL DEFAULT 30,
            claimed INTEGER DEFAULT 0,
            email TEXT DEFAULT '',
            api_key TEXT DEFAULT '',
            batch_id TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            claimed_at TEXT
        )
    """)
    # 确保 api_keys 表有 plan 列
    try:
        conn.execute("ALTER TABLE api_keys ADD COLUMN plan TEXT DEFAULT 'free'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def _generate_code(length=8) -> str:
    """生成短码: IG-XXXXXXX"""
    chars = string.ascii_uppercase + string.digits
    code = ''.join(secrets.choice(chars) for _ in range(length))
    return f"IG-{code}"


def _create_api_key(email: str, plan: str, credits: int) -> str:
    """创建 API Key"""
    new_key = f"ig_{secrets.token_hex(16)}"
    conn = _get_db()
    conn.execute(
        "INSERT INTO api_keys (key, email, plan, credits_remaining, credits_total) VALUES (?, ?, ?, ?, ?)",
        (new_key, email, plan, credits, credits),
    )
    conn.commit()
    conn.close()
    return new_key


# ═══════════════════════════════════════════════
# 固定页面
# ═══════════════════════════════════════════════

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
.feature p { color: #666; }
.how { background: #f8f9fa; padding: 60px 20px; text-align: center; }
.steps { max-width: 700px; margin: 0 auto; display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }
.step { background: white; border-radius: 12px; padding: 24px; flex: 1; min-width: 180px; }
.step .num { background: #667eea; color: white; width: 32px; height: 32px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 12px; font-weight: bold; }
.footer { text-align: center; padding: 32px; color: #999; font-size: 0.85em; }
.tag { display: inline-block; background: #e74c3c; color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.75em; margin-top: 8px; }
</style></head>
<body>
<div class="hero">
  <h1>📝 IELTS Grader</h1>
  <p>AI 雅思写作批改 · 四维评分 · 分段画像 · 提分路线图</p>
  <div>
    <a class="btn" href="/pricing">开始使用 →</a>
    <a class="btn outline" href="/claim">已有激活码？</a>
  </div>
</div>
<div class="features">
  <div class="feature"><div class="icon">🎯</div><h3>四维评分</h3><p>TA/CC/LR/GRA 精确评分</p></div>
  <div class="feature"><div class="icon">📊</div><h3>分段画像</h3><p>定位你的真实水平</p></div>
  <div class="feature"><div class="icon">🗺️</div><h3>提分路线图</h3><p>分周执行计划</p></div>
  <div class="feature"><div class="icon">❌</div><h3>语法定位</h3><p>精准打击弱项</p></div>
</div>
<div class="how">
  <h2>购买方式</h2>
  <div class="steps">
    <div class="step"><div class="num">1</div><h3>在线支付</h3><p>微信/支付宝<br>即时到账</p><a href="/pricing" style="color:#667eea;font-size:0.85em;">→ 去购买</a></div>
    <div class="step"><div class="num">2</div><h3>闲鱼/淘宝</h3><p>搜索 IELTS Grader<br>购买后获激活码</p><a href="/claim" style="color:#667eea;font-size:0.85em;">→ 激活码领用</a></div>
  </div>
</div>
<div class="footer"><p>微信/支付宝支付 · 闲鱼/淘宝搜索 IELTS Grader</p></div>
</body></html>"""


# ── 激活码领用页 ──

CLAIM_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>激活码领用 - IELTS Grader</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, 'PingFang SC', sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
.card { background: white; border-radius: 20px; padding: 40px 32px; max-width: 420px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.15); text-align: center; }
.card h1 { margin-bottom: 8px; }
.card p { color: #666; margin-bottom: 24px; }
.input { width: 100%; padding: 14px; border: 2px solid #ddd; border-radius: 10px; font-size: 1em; text-align: center; letter-spacing: 2px; margin: 8px 0; font-weight: 600; }
.input:focus { border-color: #667eea; outline: none; }
.btn { width: 100%; background: #667eea; color: white; border: none; padding: 14px; border-radius: 10px; font-size: 1em; cursor: pointer; margin-top: 8px; }
.btn:hover { background: #5a6fd6; }
.btn:disabled { opacity: 0.5; }
#result { margin-top: 16px; padding: 12px; border-radius: 8px; display: none; font-size: 0.9em; }
#result.success { display: block; background: #e8f8f5; color: #27ae60; }
#result.error { display: block; background: #fdf2e9; color: #e74c3c; }
.hint { font-size: 0.8em; color: #999; margin-top: 8px; }
</style></head>
<body>
<div class="card">
  <h1>🎟️ 激活码领用</h1>
  <p>在闲鱼/淘宝购买后，输入激活码领取你的 API Key</p>
  <input class="input" id="code" placeholder="IG-XXXXXXXX" style="text-transform:uppercase;" maxlength="11">
  <input class="input" id="email" placeholder="你的邮箱" type="email" style="letter-spacing:0;">
  <button class="btn" onclick="claimCode()">🎯 领取</button>
  <div id="result"></div>
  <div class="hint">没有激活码？<a href="/pricing" style="color:#667eea;">去购买 →</a></div>
</div>
<script>
async function claimCode() {
  const code = document.getElementById('code').value.trim().toUpperCase();
  const email = document.getElementById('email').value.trim();
  if (!code) { alert('请输入激活码'); return; }
  if (!email) { alert('请输入邮箱'); return; }
  const btn = document.querySelector('.btn');
  btn.textContent = '⏳ 处理中...'; btn.disabled = true;
  const result = document.getElementById('result');
  try {
    const resp = await fetch('/v1/claim', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ code, email }),
    });
    const data = await resp.json();
    if (data.api_key) {
      result.className = 'success';
      result.innerHTML = '✅ 激活成功！<br>正在跳转控制台...';
      setTimeout(() => window.location.href = '/dashboard?key=' + data.api_key, 1500);
    } else {
      result.className = 'error';
      result.innerHTML = '❌ ' + (data.error || '激活失败');
    }
  } catch(e) {
    result.className = 'error';
    result.innerHTML = '❌ 网络错误';
  }
  btn.textContent = '🎯 领取'; btn.disabled = false;
}
</script>
</body></html>"""


# ═══════════════════════════════════════════════
# 路由
# ═══════════════════════════════════════════════

@router.get("/landing", response_class=HTMLResponse)
def landing():
    _init_tables()
    return LANDING_HTML


@router.get("/claim", response_class=HTMLResponse)
def claim_page():
    _init_tables()
    return CLAIM_HTML


@router.post("/v1/claim")
def claim_code(data: dict):
    """激活码领用：验证码 → 创建 API Key"""
    code = data.get("code", "").strip().upper()
    email = data.get("email", "").strip()

    if not code or not email:
        raise HTTPException(400, "激活码和邮箱不能为空")

    conn = _get_db()
    row = conn.execute("SELECT * FROM activation_codes WHERE code = ?", (code,)).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(404, "激活码不存在")

    if row["claimed"]:
        conn.close()
        raise HTTPException(409, "该激活码已被领用")

    # 创建 API Key
    new_key = _create_api_key(email, row["plan"], row["credits"])

    # 标记已领用
    conn.execute(
        "UPDATE activation_codes SET claimed=1, email=?, api_key=?, claimed_at=datetime('now') WHERE code=?",
        (email, new_key, code),
    )
    conn.commit()
    conn.close()

    return {"success": True, "api_key": new_key, "credits": row["credits"], "plan": row["plan"]}


# ═══════════════════════════════════════════════
# 管理后台 — 批量生成激活码
# ═══════════════════════════════════════════════

ADMIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>管理后台 - IELTS Grader</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; padding: 24px; max-width: 1000px; margin: 0 auto; }
h1 { margin-bottom: 24px; }
.card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.card h3 { margin-bottom: 12px; }
.row { display: flex; gap: 12px; align-items: end; flex-wrap: wrap; }
.row > * { flex: 1; min-width: 120px; }
label { display: block; font-size: 0.85em; color: #666; margin-bottom: 4px; }
select, input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px; }
.btn { background: #667eea; color: white; border: none; padding: 10px 24px; border-radius: 8px; cursor: pointer; }
.btn:hover { background: #5a6fd6; }
.btn.green { background: #27ae60; }
.btn.small { padding: 6px 12px; font-size: 0.85em; }
table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
th, td { padding: 8px 6px; text-align: left; border-bottom: 1px solid #eee; }
th { color: #666; }
.code { font-family: monospace; font-size: 1.1em; letter-spacing: 1px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
.badge.used { background: #e8f8f5; color: #27ae60; }
.badge.new { background: #fef9e7; color: #f39c12; }
.copy-btn { cursor: pointer; color: #667eea; }
.copy-btn:hover { text-decoration: underline; }
.tip { background: #eaf2f8; padding: 12px; border-radius: 8px; margin-bottom: 16px; font-size: 0.9em; color: #2c3e50; }
.tip strong { color: #e74c3c; }
</style></head>
<body>
<div class="tip">
  <strong>🏪 闲鱼/淘宝商家操作指南</strong><br>
  1. 选方案 + 数量 → 点"生成" → 拿到激活码列表<br>
  2. 在闲鱼/淘宝上架商品，标题写 "IELTS Grader 雅思写作批改"<br>
  3. 顾客下单后 → 发一个激活码给顾客（或打印二维码贴在包装里）<br>
  4. 顾客访问 /claim 输入激活码 → 自动获得 API Key
</div>

<h1>📊 激活码管理</h1>

<div class="card">
  <h3>➕ 批量生成激活码</h3>
  <div class="row">
    <div>
      <label>方案</label>
      <select id="planSelect">
        <option value="starter">基础版 (30次 ¥19.9)</option>
        <option value="pro" selected>专业版 (100次 ¥59.9)</option>
        <option value="unlimited">无限版 (9999次 ¥199)</option>
      </select>
    </div>
    <div>
      <label>数量</label>
      <input type="number" id="countInput" value="5" min="1" max="50">
    </div>
    <div>
      <button class="btn green" onclick="generateBatch()">⚡ 生成</button>
    </div>
  </div>
</div>

<div class="card">
  <h3>📋 已生成激活码 <span id="codeCount" style="font-weight:normal;color:#999;font-size:0.85em;"></span></h3>
  <div style="margin-bottom:8px;">
    <button class="btn small" onclick="copyAll()">📋 复制所有未领用</button>
    <button class="btn small" onclick="loadCodes()">🔄 刷新</button>
  </div>
  <div style="overflow-x:auto;">
    <table><thead><tr>
      <th>激活码</th><th>方案</th><th>状态</th><th>邮箱</th><th>API Key</th><th>时间</th>
    </tr></thead><tbody id="codeTable"></tbody></table>
  </div>
</div>

<script>
const ADMIN_KEY = prompt('请输入管理员密码（ADMIN_API_KEY）：') || '';

async function generateBatch() {
  const plan = document.getElementById('planSelect').value;
  const count = parseInt(document.getElementById('countInput').value) || 5;
  const btn = event.target;
  btn.textContent = '⏳ 生成中...'; btn.disabled = true;
  try {
    const resp = await fetch('/v1/admin/batch-codes', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'admin-key': ADMIN_KEY},
      body: JSON.stringify({ plan, count }),
    });
    if (!resp.ok) { alert('生成失败: ' + await resp.text()); return; }
    const data = await resp.json();
    alert('✅ 成功生成 ' + data.codes.length + ' 个激活码！\\n\\n' + data.codes.join('\\n'));
    loadCodes();
  } catch(e) { alert('网络错误'); }
  btn.textContent = '⚡ 生成'; btn.disabled = false;
}

async function loadCodes() {
  try {
    const resp = await fetch('/v1/admin/codes', {
      headers: { 'admin-key': ADMIN_KEY },
    });
    if (!resp.ok) { document.getElementById('codeTable').innerHTML = '<tr><td colspan="6" style="text-align:center;color:#999;">请检查管理员密码</td></tr>'; return; }
    const data = await resp.json();
    const tbody = document.getElementById('codeTable');
    document.getElementById('codeCount').textContent = '(共 ' + data.codes.length + ' 个)';
    if (data.codes.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#999;padding:20px;">暂无激活码，在上方生成</td></tr>';
      return;
    }
    const planNames = {'starter':'基础版','pro':'专业版','unlimited':'无限版'};
    tbody.innerHTML = data.codes.map(c => '<tr>' +
      '<td class="code" onclick="navigator.clipboard.writeText(\'' + c.code + '\');this.style.color=\'green\'">' + c.code + '</td>' +
      '<td>' + (planNames[c.plan] || c.plan) + '</td>' +
      '<td><span class="badge ' + (c.claimed ? 'used' : 'new') + '">' + (c.claimed ? '已领用' : '待领取') + '</span></td>' +
      '<td>' + (c.email || '-') + '</td>' +
      '<td style="font-size:0.8em;">' + (c.api_key ? c.api_key.substring(0, 20) + '...' : '-') + '</td>' +
      '<td>' + (c.created_at || '').substring(0, 10) + '</td>' +
    '</tr>').join('');
  } catch(e) { document.getElementById('codeTable').innerHTML = '<tr><td colspan="6" style="color:#999;">加载失败</td></tr>'; }
}

function copyAll() {
  const rows = document.querySelectorAll('#codeTable tr');
  const codes = [];
  rows.forEach(row => {
    const cells = row.querySelectorAll('td');
    if (cells.length >= 3 && cells[2].textContent.trim() === '待领取') {
      codes.push(cells[0].textContent.trim());
    }
  });
  if (codes.length === 0) { alert('没有待领用的激活码'); return; }
  navigator.clipboard.writeText(codes.join('\\n'));
  alert('✅ 已复制 ' + codes.length + ' 个激活码');
}

loadCodes();
</script>
</body></html>"""


@router.get("/admin", response_class=HTMLResponse)
def admin_page():
    _init_tables()
    return ADMIN_HTML


@router.post("/v1/admin/batch-codes")
def batch_create_codes(data: dict, admin_key: str = Header(None)):
    """批量生成激活码（管理员）"""
    import os
    expected = os.environ.get("ADMIN_API_KEY", "")
    if not expected or admin_key != expected:
        raise HTTPException(403, "需要管理员权限")

    plan = data.get("plan", "pro")
    count = min(data.get("count", 5), 50)
    plan_info = PLANS.get(plan, PLANS["pro"])
    batch_id = secrets.token_hex(4)

    conn = _get_db()
    codes = []
    for _ in range(count):
        code = _generate_code()
        conn.execute(
            "INSERT OR IGNORE INTO activation_codes (code, plan, credits, batch_id) VALUES (?, ?, ?, ?)",
            (code, plan, plan_info["credits"], batch_id),
        )
        codes.append(code)
    conn.commit()
    conn.close()

    return {"batch_id": batch_id, "codes": codes, "count": len(codes)}


@router.get("/v1/admin/codes")
def list_codes(admin_key: str = Header(None)):
    """列出所有激活码（管理员）"""
    import os
    expected = os.environ.get("ADMIN_API_KEY", "")
    if not expected or admin_key != expected:
        raise HTTPException(403, "需要管理员权限")

    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM activation_codes ORDER BY created_at DESC LIMIT 200"
    ).fetchall()
    conn.close()

    return {"codes": [dict(r) for r in rows]}
