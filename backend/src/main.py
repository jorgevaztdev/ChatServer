import asyncio
import json
import re
from collections import defaultdict
from time import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.models.base import init_db
from src.api import router as api_router

# ── T074: HTML sanitization (pure ASGI middleware — avoids body-cache conflict) ──

def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _sanitize(obj):
    if isinstance(obj, str):
        return _strip_html(obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(i) for i in obj]
    return obj


class _SanitizeMiddleware:
    """Strip HTML tags from all incoming JSON string fields (XSS prevention)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("method") in ("POST", "PUT", "PATCH"):
            headers = {k: v for k, v in scope.get("headers", [])}
            ct = headers.get(b"content-type", b"").decode("utf-8", errors="ignore")
            if "application/json" in ct:
                chunks: list[bytes] = []
                more_body = True
                while more_body:
                    msg = await receive()
                    chunks.append(msg.get("body", b""))
                    more_body = msg.get("more_body", False)

                body = b"".join(chunks)
                try:
                    body = json.dumps(_sanitize(json.loads(body))).encode()
                except Exception:
                    pass

                done = False

                async def _sanitized_receive():
                    nonlocal done
                    if not done:
                        done = True
                        return {"type": "http.request", "body": body, "more_body": False}
                    return await receive()

                await self.app(scope, _sanitized_receive, send)
                return

        await self.app(scope, receive, send)


# ── T073: Login rate limiting ─────────────────────────────────────────────────

_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60.0
_RATE_MAX = 10
# Loopback addresses are exempt (covers TestClient and local dev)
_RATE_EXEMPT = {"127.0.0.1", "::1", "testclient"}


def _get_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


app = FastAPI(title="Chat Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(_SanitizeMiddleware)


@app.middleware("http")
async def rate_limit_login(request: Request, call_next):
    if request.url.path == "/auth/login" and request.method == "POST":
        ip = _get_ip(request)
        if ip not in _RATE_EXEMPT:
            now = time()
            _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _RATE_WINDOW]
            if len(_login_attempts[ip]) >= _RATE_MAX:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many login attempts — try again in a minute"},
                )
            _login_attempts[ip].append(now)
    return await call_next(request)


app.include_router(api_router)


# ── T075: Enhanced health endpoint ───────────────────────────────────────────

@app.get("/health")
async def health():
    import os
    import tempfile
    from sqlalchemy import text
    from src.models.base import SessionLocal
    from src.config import MEDIA_DIR

    db_status = "error"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "ok"
    except Exception:
        pass

    media_status = "error"
    try:
        with tempfile.NamedTemporaryFile(dir=MEDIA_DIR, delete=True):
            media_status = "writable"
    except Exception:
        pass

    return {"status": "ok", "db": db_status, "media_dir": media_status}


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    from src.services.presence import run_afk_checker
    asyncio.create_task(run_afk_checker())
    from src.services.jabber_server import start_jabber_server
    asyncio.create_task(start_jabber_server())
