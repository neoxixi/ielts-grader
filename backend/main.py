"""
IELTS Grader SaaS Backend — FastAPI 服务

提供:
  POST /v1/grade  — 作文评分 API（需 API Key）
  GET  /v1/me     — 查询剩余次数
  POST /v1/keys   — 创建 API Key（管理员）

部署:
  uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""

import os, json, secrets
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── 将项目根目录加入 sys.path ──
import sys
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ielts_grader.grader import grade_essay
from ielts_grader.core import build_enriched_report
from ielts_grader._private import _has_private_data
from ielts_grader.report import render_html


# ═══════════════════════════════════════════════
# 数据库（SQLite，零配置）
# ═══════════════════════════════════════════════

_DB_PATH = Path(__file__).parent / "data" / "saas.db"

def _init_db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key TEXT PRIMARY KEY,
            email TEXT,
            plan TEXT DEFAULT 'free',
            credits_remaining INTEGER DEFAULT 5,
            credits_total INTEGER DEFAULT 5,
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT,
            endpoint TEXT,
            word_count INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Seed admin key
    admin_key = os.environ.get("ADMIN_API_KEY", "")
    if admin_key:
        conn.execute(
            "INSERT OR IGNORE INTO api_keys (key, email, plan, credits_remaining, credits_total) VALUES (?, ?, ?, 999999, 999999)",
            (admin_key, "admin@local", "admin"),
        )
    conn.commit()
    conn.close()

def _get_key_info(api_key: str) -> dict | None:
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM api_keys WHERE key = ?", (api_key,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)

def _use_credit(api_key: str):
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("UPDATE api_keys SET credits_remaining = MAX(0, credits_remaining - 1) WHERE key = ?", (api_key,))
    conn.commit()
    conn.close()

def _log_usage(api_key: str, word_count: int):
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute(
        "INSERT INTO usage_log (api_key, endpoint, word_count) VALUES (?, 'grade', ?)",
        (api_key, word_count),
    )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════
# Pydantic 模型
# ═══════════════════════════════════════════════

class GradeRequest(BaseModel):
    essay: str
    task_type: str = "T2"
    format: str = "json"  # json | html

class GradeResponse(BaseModel):
    success: bool
    overall_band: float | None = None
    dimensions: dict = {}
    band_profile: dict = {}
    recommendations: dict = {}
    html: str | None = None
    error: str | None = None
    credits_remaining: int = 0


# ═══════════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_db()
    yield

app = FastAPI(
    title="IELTS Grader API",
    version="1.0.0",
    description="雅思写作 AI 批改 API — 四维评分 + 专家知识库增强",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 静态文件（收款码图片等）
from fastapi.staticfiles import StaticFiles
import os
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# 注册支付路由
from .payments import router as payments_router, PRICING_PAGE_HTML, PRICING
app.include_router(payments_router)

# 注册前端页面路由
from .pages import router as pages_router
app.include_router(pages_router)


# ═══════════════════════════════════════════════
# 认证
# ═══════════════════════════════════════════════

async def verify_key(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "缺少 API Key。在 Header 中传入: Authorization: Bearer <your_key>")
    api_key = authorization.replace("Bearer ", "").strip()
    info = _get_key_info(api_key)
    if info is None:
        raise HTTPException(403, "API Key 无效")
    if info["credits_remaining"] <= 0 and info["plan"] != "admin":
        raise HTTPException(402, "额度已用完，请充值")
    return info


# ═══════════════════════════════════════════════
# API 路由
# ═══════════════════════════════════════════════

@app.get("/")
def root():
    return {"service": "IELTS Grader API", "version": "1.0.0", "docs": "/docs"}


@app.get("/pricing")
def pricing_page():
    from fastapi.responses import HTMLResponse
    return HTMLResponse(PRICING_PAGE_HTML)


@app.get("/v1/keys/free")
def create_free_key():
    """免费试用：创建 3 次额度的 API Key"""
    new_key = f"ig_{secrets.token_hex(16)}"
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute(
        "INSERT INTO api_keys (key, email, plan, credits_remaining, credits_total) VALUES (?, ?, ?, ?, ?)",
        (new_key, "free@user", "free", 3, 3),
    )
    conn.commit()
    conn.close()
    return {
        "api_key": new_key,
        "credits": 3,
        "message": "Free trial key created. 3 credits remaining.",
        "pricing": "/pricing",
    }


@app.get("/v1/me")
def me(key_info: dict = Depends(verify_key)):
    return {
        "plan": key_info["plan"],
        "credits_remaining": key_info["credits_remaining"],
        "credits_total": key_info["credits_total"],
    }


@app.post("/v1/grade")
async def grade(req: GradeRequest, key_info: dict = Depends(verify_key)):
    # 校验
    if not req.essay or len(req.essay.strip()) < 20:
        raise HTTPException(400, "作文太短（至少20字）")
    if req.task_type not in ("T1", "T2"):
        raise HTTPException(400, "task_type 必须是 T1 或 T2")

    # 检查是否有完整知识库
    if not _has_private_data():
        raise HTTPException(503, "服务器未配置完整知识库，请联系管理员")

    # 评分
    try:
        llm_result = grade_essay(req.essay, req.task_type, verbose=False)
        enriched = build_enriched_report(llm_result, req.essay, req.task_type)
    except Exception as e:
        raise HTTPException(500, f"评分失败: {e}")

    # 扣减额度
    api_key = key_info["key"]
    _use_credit(api_key)
    _log_usage(api_key, enriched.get("word_count", 0))

    # 构造响应
    resp = {
        "success": True,
        "overall_band": enriched["overall_band"],
        "dimensions": enriched.get("dimensions", {}),
        "band_profile": enriched.get("band_profile", {}),
        "recommendations": enriched.get("enriched_recommendations", {}),
        "credits_remaining": key_info["credits_remaining"] - 1,
        "error": None,
    }

    if req.format == "html":
        resp["html"] = render_html(enriched)

    return resp


# ═══════════════════════════════════════════════
# 管理员: 创建 API Key
# ═══════════════════════════════════════════════

class CreateKeyRequest(BaseModel):
    email: str
    plan: str = "pro"
    credits: int = 100

@app.post("/v1/keys")
def create_key(req: CreateKeyRequest, admin_key: str = Header(None)):
    expected = os.environ.get("ADMIN_API_KEY", "")
    if not expected or admin_key != expected:
        raise HTTPException(403, "需要管理员权限")

    new_key = f"ig_{secrets.token_hex(16)}"
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute(
        "INSERT INTO api_keys (key, email, plan, credits_remaining, credits_total) VALUES (?, ?, ?, ?, ?)",
        (new_key, req.email, req.plan, req.credits, req.credits),
    )
    conn.commit()
    conn.close()
    return {"api_key": new_key, "email": req.email, "plan": req.plan, "credits": req.credits}


# ═══════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
