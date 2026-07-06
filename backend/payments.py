"""
支付模块 — 微信支付 / 支付宝

模式:
  1. 虎皮椒聚合支付（生产推荐，个人可接入）
     https://www.xorpay.com/ 或 https://www.hupijiao.com/
  2. 收款码模式（MVP 快速验证）
     生成付款码 → 用户扫码付 → 人工确认到账 → 系统发 Key

环境变量:
  PAYMENT_PROVIDER=hupijiao  | manual  (默认 manual)
  HUPIJIAO_APP_ID=xxx
  HUPIJIAO_APP_SECRET=xxx
  HUPIJIAO_WEBHOOK_SECRET=xxx
  MANUAL_QR_WECHAT=/static/qr_wechat.jpg  (收款码图片路径)
  MANUAL_QR_ALIPAY=/static/qr_alipay.jpg
"""

import os, json, secrets, hashlib, hmac, sqlite3
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Header, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

router = APIRouter(prefix="/v1/payments", tags=["payments"])

_DB_PATH = Path(__file__).parent / "data" / "saas.db"

# ── 定价方案（人民币） ──
PRICING = {
    "free": {"name": "免费试用", "credits": 3, "price_cny": 0, "desc": "试试看"},
    "starter": {"name": "基础版", "credits": 30, "price_cny": 19.9, "desc": "适合偶尔练习"},
    "pro": {"name": "专业版", "credits": 100, "price_cny": 59.9, "desc": "适合认真备考"},
    "unlimited": {"name": "无限版", "credits": 9999, "price_cny": 199, "desc": "无限评分+优先支持"},
}


def _get_db():
    db_path = _DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _create_api_key(email: str, plan: str, credits: int) -> str:
    """创建 API Key 并写入数据库"""
    new_key = f"ig_{secrets.token_hex(16)}"
    conn = _get_db()
    conn.execute(
        "INSERT INTO api_keys (key, email, plan, credits_remaining, credits_total) VALUES (?, ?, ?, ?, ?)",
        (new_key, email, plan, credits, credits),
    )
    conn.commit()
    conn.close()
    return new_key


def _get_provider() -> str:
    return os.environ.get("PAYMENT_PROVIDER", "manual")


# ═══════════════════════════════════════════════
# 模式 A: 虎皮椒聚合支付
# ═══════════════════════════════════════════════

def _hupijiao_create_order(plan: str, email: str, trade_no: str) -> dict:
    """向虎皮椒提交订单"""
    import httpx
    app_id = os.environ.get("HUPIJIAO_APP_ID", "")
    app_secret = os.environ.get("HUPIJIAO_APP_SECRET", "")
    plan_info = PRICING.get(plan, PRICING["pro"])
    amount = str(plan_info["price_cny"])

    notify_url = os.environ.get(
        "APP_URL", "http://localhost:8000") + "/v1/payments/hupijiao-webhook"
    return_url = os.environ.get(
        "APP_URL", "http://localhost:8000") + f"/v1/payments/success?plan={plan}"

    sign_str = f"{app_id}{amount}{notify_url}{trade_no}{app_secret}"
    sign = hashlib.md5(sign_str.encode()).hexdigest()

    resp = httpx.post(
        "https://api.xorpay.com/api/order",
        data={
            "appid": app_id,
            "price": amount,
            "trade_no": trade_no,
            "notify_url": notify_url,
            "return_url": return_url,
            "sign": sign,
        },
    )
    return resp.json()


@router.post("/hupijiao-webhook")
async def hupijiao_webhook(request: Request):
    """虎皮椒支付回调"""
    form = await request.form()
    data = dict(form)
    app_secret = os.environ.get("HUPIJIAO_APP_SECRET", "")

    # 验证签名
    sign_str = f"{data.get('trade_no', '')}{data.get('money', '')}{app_secret}"
    expected = hashlib.md5(sign_str.encode()).hexdigest()
    if data.get("sign", "") != expected:
        raise HTTPException(401, "签名无效")

    # 解析 trade_no 获取 plan 和 email
    trade_no = data.get("trade_no", "")
    parts = trade_no.split("_")
    if len(parts) >= 3:
        plan = parts[1]
        email = parts[2]
        plan_info = PRICING.get(plan, PRICING["pro"])
        _create_api_key(email, plan, plan_info["credits"])

    return {"status": "success"}


# ═══════════════════════════════════════════════
# 模式 B: 收款码（MVP 快速验证）
# ═══════════════════════════════════════════════

@router.get("/manual-qr")
def manual_qr(plan: str = "pro"):
    """显示收款码页面"""
    plan_info = PRICING.get(plan, PRICING["pro"])
    price = plan_info["price_cny"]

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>付款 - IELTS Grader</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, 'PingFang SC', sans-serif; background: #f5f5f5; text-align: center; padding: 32px 16px; }}
.card {{ background: white; border-radius: 16px; max-width: 400px; margin: 0 auto; padding: 32px 24px; box-shadow: 0 2px 16px rgba(0,0,0,0.1); }}
h1 {{ font-size: 1.5em; margin-bottom: 8px; }}
.price {{ font-size: 2.5em; font-weight: bold; color: #e74c3c; margin: 16px 0; }}
.price span {{ font-size: 0.4em; color: #999; }}
.qr-grid {{ display: flex; gap: 16px; justify-content: center; margin: 20px 0; }}
.qr-box {{ flex: 1; padding: 16px; background: #fafafa; border-radius: 12px; }}
.qr-box img {{ width: 140px; height: 140px; }}
.qr-box p {{ margin-top: 8px; font-size: 0.85em; color: #666; }}
.btn {{ display: block; background: #27ae60; color: white; text-decoration: none; padding: 14px; border-radius: 8px; font-size: 1.1em; margin: 16px 0; }}
.btn:hover {{ opacity: 0.9; }}
.tip {{ font-size: 0.85em; color: #999; margin-top: 12px; }}
.input {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px; margin: 8px 0; font-size: 1em; }}
</style></head>
<body>
<div class="card">
  <h1>IELTS Grader</h1>
  <p>{plan_info['name']}</p>
  <div class="price">¥{price}<span> 人民币</span></div>
  <p>{plan_info['credits']} 次评分</p>

  <div class="qr-grid">
    <div class="qr-box">
      <img src="/static/qr_wechat.jpg" alt="微信支付" onerror="this.outerHTML='<div style=padding:40px;color:#999>请配置微信收款码</div>'">
      <p>微信支付</p>
    </div>
    <div class="qr-box">
      <img src="/static/qr_alipay.jpg" alt="支付宝" onerror="this.outerHTML='<div style=padding:40px;color:#999>请配置支付宝收款码</div>'">
      <p>支付宝</p>
    </div>
  </div>

  <input class="input" id="email" placeholder="你的邮箱（用于接收 API Key）">
  <button class="btn" onclick="submitPay()">✅ 我已付款，领取 Key</button>
  <div id="result" style="margin-top:12px;font-size:0.9em;color:#666;"></div>
  <div class="tip">付款后点击上方按钮，系统自动发放 API Key</div>
</div>

<script>
async function submitPay() {{
  const email = document.getElementById('email').value;
  if (!email) {{ alert('请输入邮箱'); return; }}
  const btn = document.querySelector('.btn');
  btn.textContent = '⏳ 处理中...'; btn.disabled = true;
  try {{
    const resp = await fetch('/v1/payments/manual-confirm', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ plan: '{plan}', email }}),
    }});
    const data = await resp.json();
    if (data.api_key) {{
      document.getElementById('result').innerHTML = '✅ Key 已生成！跳转控制台...';
      setTimeout(() => window.location.href = '/dashboard?key=' + data.api_key, 1500);
    }} else {{
      document.getElementById('result').innerHTML = '❌ ' + (data.error || '处理失败');
    }}
  }} catch(e) {{
    document.getElementById('result').innerHTML = '❌ 网络错误';
  }}
  btn.textContent = '✅ 我已付款，领取 Key'; btn.disabled = false;
}}
</script>
</body></html>""")


@router.post("/manual-confirm")
async def manual_confirm(data: dict):
    """
    收款码模式确认：用户付款后手动点击"我已付款"
    生产环境建议接虎皮椒自动回调，此模式用于 MVP 快速验证
    """
    plan = data.get("plan", "pro")
    email = data.get("email", f"user_{secrets.token_hex(4)}@manual")
    plan_info = PRICING.get(plan)

    if not plan_info:
        raise HTTPException(400, "无效方案")

    # 创建 API Key
    new_key = _create_api_key(email, plan, plan_info["credits"])

    return {
        "success": True,
        "api_key": new_key,
        "credits": plan_info["credits"],
        "plan": plan,
        "message": f"{plan_info['name']} 已激活！请在 API 请求中使用此 Key。",
    }


# ═══════════════════════════════════════════════
# 通用 checkout 路由（合并微信/支付宝/虎皮椒）
# ═══════════════════════════════════════════════

class CheckoutRequest(BaseModel):
    plan: str = "pro"
    email: str = ""

@router.post("/checkout")
async def checkout(req: CheckoutRequest):
    """创建支付订单"""
    plan_info = PRICING.get(req.plan)
    if not plan_info:
        raise HTTPException(400, f"无效方案: {req.plan}")

    provider = _get_provider()

    if provider == "hupijiao":
        # 虎皮椒支付
        trade_no = f"ig_{req.plan}_{req.email or 'user'}_{secrets.token_hex(4)}"
        result = _hupijiao_create_order(req.plan, req.email, trade_no)
        return {
            "pay_url": result.get("url", ""),
            "qr_code": result.get("qrcode", ""),
            "trade_no": trade_no,
            "amount": plan_info["price_cny"],
        }
    else:
        # 收款码模式 — 重定向到付款页面
        return {
            "pay_url": f"/v1/payments/manual-qr?plan={req.plan}",
            "amount": plan_info["price_cny"],
            "plan": req.plan,
        }


@router.get("/checkout-redirect/{plan}")
async def checkout_redirect(plan: str, email: str = ""):
    """定价页面 → 跳转支付"""
    if plan == "free":
        return RedirectResponse(url="/v1/keys/free")

    plan_info = PRICING.get(plan)
    if not plan_info:
        return {"error": "无效方案", "pricing": "/pricing"}

    provider = os.environ.get("PAYMENT_PROVIDER", "manual")

    if provider == "hupijiao":
        trade_no = f"ig_{plan}_{email or 'user'}_{secrets.token_hex(4)}"
        result = _hupijiao_create_order(plan, email, trade_no)
        pay_url = result.get("url", "")
        if pay_url:
            return RedirectResponse(url=pay_url)
        return {"error": "创建订单失败", "detail": result}

    # 收款码模式
    return RedirectResponse(url=f"/v1/payments/manual-qr?plan={plan}")


@router.get("/success")
def payment_success(plan: str = "pro"):
    plan_info = PRICING.get(plan, {})
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>支付成功</title>
<meta name="viewport" content="width=device-width">
<style>
body {{ font-family: -apple-system, 'PingFang SC', sans-serif; text-align: center; padding: 48px 16px; background: #f0f2f5; }}
.card {{ background: white; border-radius: 16px; max-width: 400px; margin: 0 auto; padding: 32px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
h1 {{ color: #27ae60; }} .big {{ font-size: 3em; }}
.detail {{ color: #666; margin: 16px 0; }}
</style></head>
<body>
<div class="card">
  <div class="big">✅</div>
  <h1>支付成功！</h1>
  <p class="detail">{plan_info.get('name', '')} 方案已激活</p>
  <p class="detail">{plan_info.get('credits', 0)} 次评分额度</p>
  <p>API Key 已发送到你的邮箱（或返回获取）</p>
  <p style="margin-top:24px;"><a href="/v1/me" style="color:#667eea;">查看我的额度 →</a></p>
</div>
</body></html>""")


# ═══════════════════════════════════════════════
# 定价页面 HTML（中文）
# ═══════════════════════════════════════════════

PRICING_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>IELTS Grader - 定价</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; }
.header { text-align: center; padding: 48px 20px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
.header h1 { font-size: 2em; margin-bottom: 8px; }
.header p { opacity: 0.9; }
.plans { max-width: 900px; margin: 32px auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; padding: 0 16px; }
.plan { background: white; border-radius: 16px; padding: 24px; text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,0.08); display: flex; flex-direction: column; }
.plan.featured { border: 2px solid #667eea; transform: scale(1.05); }
.plan h3 { font-size: 1.2em; margin-bottom: 8px; }
.plan .price { font-size: 2em; font-weight: bold; color: #e74c3c; margin: 12px 0; }
.plan .price span { font-size: 0.4em; color: #999; }
.plan .desc { color: #666; font-size: 0.9em; flex: 1; }
.plan .btn { display: block; background: #667eea; color: white; text-decoration: none; padding: 12px; border-radius: 8px; margin-top: 16px; font-weight: 600; }
.plan .btn:hover { background: #5a6fd6; }
.plan .btn.green { background: #27ae60; }
.footer { text-align: center; padding: 32px; color: #999; font-size: 0.85em; }
.features { max-width: 600px; margin: 0 auto 32px; padding: 0 16px; }
.features li { margin: 8px 0; color: #555; }
</style></head>
<body>
<div class="header">
  <h1>📝 IELTS Grader</h1>
  <p>AI 雅思写作批改 · 四维评分 · 分段画像 · 提分路线图</p>
</div>
<div class="plans" id="plans"></div>
<ul class="features">
  <li>✅ 四维评分（TA/CC/LR/GRA）+ 详细评分理由</li>
  <li>✅ 语法错误 Top3 定位 + 模板检测</li>
  <li>✅ Band 分段画像 + 专属写作策略</li>
  <li>✅ 4 周提分路线图（按 Band 定制）</li>
  <li>✅ 支持微信 / 支付宝付款</li>
</ul>
<div class="footer">
  <p>有问题？联系作者 · 付款后自动发放 API Key</p>
  <p style="margin-top:8px;">🏪 也支持 <a href="/claim" style="color:#667eea;">闲鱼/淘宝购买激活码</a>（搜索 "IELTS Grader"）</p>
</div>
<script>
const PLANS = {
  free: { name: "免费试用", credits: 3, price: "免费", desc: "试试看", featured: false, cls: "green" },
  starter: { name: "基础版", credits: 30, price: "¥19.9", desc: "适合偶尔练习", featured: false, cls: "" },
  pro: { name: "专业版", credits: 100, price: "¥59.9", desc: "适合认真备考", featured: true, cls: "" },
  unlimited: { name: "无限版", credits: "∞", price: "¥199", desc: "无限评分+优先支持", featured: false, cls: "" },
};
const container = document.getElementById('plans');
Object.entries(PLANS).forEach(([key, p]) => {
  const div = document.createElement('div');
  div.className = 'plan' + (p.featured ? ' featured' : '');
  div.innerHTML = `
    <h3>${p.name}</h3>
    <div class="price">${p.price}<span>/月</span></div>
    <div style="font-size:1.5em;font-weight:bold;color:#667eea;">${p.credits}</div>
    <div style="font-size:0.85em;color:#999;margin-bottom:8px;">次评分</div>
    <div class="desc">${p.desc}</div>
    ${p.price === "免费"
      ? '<a class="btn green" href="javascript:void(0)" onclick="getFreeTrial()">免费领取</a>'
      : '<a class="btn" href="/v1/payments/checkout-redirect/' + key + '">立即购买</a>'}
  `;
  container.appendChild(div);
function getFreeTrial() {
  const email = prompt('请输入邮箱，领取 3 次免费评分（每人终身累计3次，非每月）：');
  if (!email || !email.includes('@')) { alert('请输入有效邮箱'); return; }
  window.location.href = '/v1/keys/free?email=' + encodeURIComponent(email);
}
});
</script>
<p style="text-align:center;margin-top:8px;font-size:0.9em;">🏪 也支持 <a href="/claim" style="color:#667eea;">闲鱼/淘宝购买激活码</a>，购买后在此输入激活码领取</p>
</body></html>"""
