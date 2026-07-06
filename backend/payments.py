"""
Lemon Squeezy 支付集成

流程:
  1. 用户访问 /pricing → 点击购买 → 跳转 LS Checkout
  2. LS 处理支付 → 发 Webhook → 本模块创建 API Key
  3. 用户收到 API Key（通过 LS 的 email 或返回页面显示）

环境变量:
  LS_API_KEY=your_lemon_squeezy_api_key
  LS_STORE_ID=your_store_id
  LS_WEBHOOK_SECRET=your_webhook_secret
"""

import os, json, secrets, hmac, hashlib
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel

router = APIRouter(prefix="/v1/payments", tags=["payments"])

# ── 定价方案 ──
PRICING = {
    "free": {
        "name": "Free Trial",
        "credits": 3,
        "price_usd": 0,
        "description": "试试看",
    },
    "starter": {
        "name": "Starter",
        "credits": 30,
        "price_usd": 9.99,
        "variant_id": os.environ.get("LS_VARIANT_STARTER", ""),
        "description": "适合偶尔练习",
    },
    "pro": {
        "name": "Pro",
        "credits": 100,
        "price_usd": 29.99,
        "variant_id": os.environ.get("LS_VARIANT_PRO", ""),
        "description": "适合认真备考",
    },
    "unlimited": {
        "name": "Unlimited Monthly",
        "credits": 9999,
        "price_usd": 99.99,
        "variant_id": os.environ.get("LS_VARIANT_UNLIMITED", ""),
        "description": "无限次评分 + 优先支持",
    },
}


def _get_db():
    """获取数据库连接"""
    import sqlite3
    from pathlib import Path
    db_path = Path(__file__).parent / "data" / "saas.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ── 创建 Checkout 链接 ──

class CheckoutRequest(BaseModel):
    plan: str = "pro"
    email: str = ""

@router.post("/checkout")
def create_checkout(req: CheckoutRequest):
    """生成 Lemon Squeezy checkout 链接"""
    plan = PRICING.get(req.plan)
    if not plan or not plan.get("variant_id"):
        raise HTTPException(400, f"无效方案: {req.plan}（或在服务端配置该方案的 variant_id）")

    ls_key = os.environ.get("LS_API_KEY", "")
    if not ls_key:
        # 无 LS Key 时返回直接购买信息（开发模式）
        return {
            "checkout_url": None,
            "plan": req.plan,
            "price": plan["price_usd"],
            "note": "Lemon Squeezy 未配置，请联系作者直接购买。",
        }

    import httpx
    resp = httpx.post(
        "https://api.lemonsqueezy.com/v1/checkouts",
        headers={
            "Authorization": f"Bearer {ls_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={
            "data": {
                "type": "checkouts",
                "attributes": {
                    "store_id": int(os.environ.get("LS_STORE_ID", "0")),
                    "variant_id": int(plan["variant_id"]),
                    "checkout_data": {
                        "email": req.email,
                        "custom_price": int(plan["price_usd"] * 100),  # cents
                    },
                    "success_url": f"{os.environ.get('APP_URL', 'http://localhost:8000')}/v1/payments/success?plan={req.plan}",
                },
            }
        },
    )
    if resp.status_code != 201:
        raise HTTPException(502, f"Lemon Squeezy 错误: {resp.text}")
    data = resp.json()
    return {"checkout_url": data["data"]["attributes"]["url"], "plan": req.plan}


# ── 支付成功页面 ──

@router.get("/checkout-redirect/{plan}")
def checkout_redirect(plan: str, email: str = ""):
    """定价页面按钮 → 创建 checkout 并跳转"""
    if plan == "free":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/v1/keys/free")

    plan_info = PRICING.get(plan)
    if not plan_info or not plan_info.get("variant_id"):
        return {"error": "该方案暂未开放购买", "pricing": "/pricing"}

    import httpx
    ls_key = os.environ.get("LS_API_KEY", "")
    if not ls_key:
        # 开发模式：直接创建 API Key
        import secrets, sqlite3
        new_key = f"ig_{secrets.token_hex(16)}"
        conn = sqlite3.connect(str(Path(__file__).parent / "data" / "saas.db"))
        conn.execute(
            "INSERT INTO api_keys (key, email, plan, credits_remaining, credits_total) VALUES (?, ?, ?, ?, ?)",
            (new_key, email or "dev@local", plan, plan_info["credits"], plan_info["credits"]),
        )
        conn.commit()
        conn.close()
        return {
            "message": f"开发模式：{plan_info['name']} 方案已激活",
            "api_key": new_key,
            "credits": plan_info["credits"],
        }

    resp = httpx.post(
        "https://api.lemonsqueezy.com/v1/checkouts",
        headers={"Authorization": f"Bearer {ls_key}", "Accept": "application/json"},
        json={
            "data": {
                "type": "checkouts",
                "attributes": {
                    "store_id": int(os.environ.get("LS_STORE_ID", "0")),
                    "variant_id": int(plan_info["variant_id"]),
                    "checkout_data": {"email": email},
                    "success_url": f"{os.environ.get('APP_URL', 'http://localhost:8000')}/v1/payments/success?plan={plan}",
                },
            }
        },
    )
    if resp.status_code != 201:
        return {"error": "创建 checkout 失败", "detail": resp.text}
    checkout_url = resp.json()["data"]["attributes"]["url"]
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=checkout_url)


@router.get("/success")
def payment_success(plan: str = "pro"):
    plan_info = PRICING.get(plan, {})
    return {
        "message": "支付成功！",
        "plan": plan,
        "credits": plan_info.get("credits", 0),
        "next": "API Key 将在几秒内通过邮件发送。也可以联系作者获取。",
    }


# ── Webhook：支付后自动创建 API Key ──

@router.post("/webhook")
async def lemon_squeezy_webhook(request: Request):
    """
    Lemon Squeezy 支付成功 Webhook

    需要在 LS Dashboard 设置 Webhook URL:
    https://your-domain.com/v1/payments/webhook

    事件类型: order_created
    """
    secret = os.environ.get("LS_WEBHOOK_SECRET", "")
    body = await request.body()
    signature = request.headers.get("X-Signature", "")

    # 验证签名
    if secret:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(401, "Webhook 签名无效")

    event_data = json.loads(body)
    event_name = event_data.get("meta", {}).get("event_name", "")

    if event_name != "order_created":
        return {"status": "ignored", "event": event_name}

    # 提取订单信息
    attrs = event_data.get("data", {}).get("attributes", {})
    user_email = attrs.get("user_email", "unknown@email.com")
    variant_id = str(attrs.get("first_order_item", {}).get("variant_id", ""))

    # 匹配 variant_id → plan → credits
    credits = 0
    for plan_key, plan_val in PRICING.items():
        if plan_val.get("variant_id") == variant_id:
            credits = plan_val["credits"]
            break

    if credits == 0:
        credits = 100  # fallback

    # 生成 API Key
    new_key = f"ig_{secrets.token_hex(16)}"
    conn = _get_db()
    conn.execute(
        "INSERT INTO api_keys (key, email, plan, credits_remaining, credits_total) VALUES (?, ?, ?, ?, ?)",
        (new_key, user_email, "paid", credits, credits),
    )
    conn.commit()
    conn.close()

    return {"status": "success", "api_key": new_key, "email": user_email, "credits": credits}


# ── 定价页面 HTML ──

PRICING_PAGE_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>IELTS Grader - 定价</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; }
.header { text-align: center; padding: 48px 20px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
.header h1 { font-size: 2em; margin-bottom: 8px; }
.header p { opacity: 0.9; }
.plans { max-width: 900px; margin: 32px auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; padding: 0 16px; }
.plan { background: white; border-radius: 16px; padding: 24px; text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
.plan.featured { border: 2px solid #667eea; transform: scale(1.05); }
.plan h3 { font-size: 1.2em; margin-bottom: 8px; }
.plan .price { font-size: 2em; font-weight: bold; color: #667eea; margin: 12px 0; }
.plan .price span { font-size: 0.4em; color: #999; }
.plan .desc { color: #666; font-size: 0.9em; margin: 8px 0; }
.plan .btn { display: block; background: #667eea; color: white; text-decoration: none; padding: 12px; border-radius: 8px; margin-top: 16px; font-weight: 600; }
.plan .btn:hover { background: #5a6fd6; }
.footer { text-align: center; padding: 32px; color: #999; font-size: 0.85em; }
</style></head>
<body>
<div class="header">
  <h1>📝 IELTS Grader</h1>
  <p>AI 雅思写作批改 · 四维评分 · 分段画像 · 提分路线图</p>
</div>
<div class="plans" id="plans"></div>
<div class="footer">
  <p>有问题？联系作者 · 所有价格含税 · 随时取消</p>
</div>
<script>
const PLANS = {
  free: { name: "Free Trial", credits: 3, price: 0, desc: "试试看", featured: false },
  starter: { name: "Starter", credits: 30, price: "$9.99", desc: "适合偶尔练习", featured: false },
  pro: { name: "Pro", credits: 100, price: "$29.99", desc: "适合认真备考", featured: true },
  unlimited: { name: "Unlimited", credits: "∞", price: "$99.99", desc: "无限评分+优先支持", featured: false },
};
const container = document.getElementById('plans');
Object.entries(PLANS).forEach(([key, p]) => {
  const div = document.createElement('div');
  div.className = 'plan' + (p.featured ? ' featured' : '');
  div.innerHTML = `
    <h3>${p.name}</h3>
    <div class="price">${p.price}<span>/月</span></div>
    <div>${p.credits} 次评分</div>
    <div class="desc">${p.desc}</div>
    ${p.price === 0 ? '<a class="btn" href="/v1/keys/free">免费领取</a>'
      : '<a class="btn" href="/v1/payments/checkout-redirect/' + key + '">立即购买</a>'}
  `;
  container.appendChild(div);
});
</script>
</body></html>
"""
