"""Đăng nhập đơn giản (1 tài khoản dùng chung) bảo vệ toàn bộ dashboard.

Dùng session cookie ký bằng SESSION_SECRET (bắt buộc set qua biến môi trường khi
deploy thật — xem README phần Deploy). Không lưu mật khẩu dạng plaintext trong
code, chỉ so sánh với biến môi trường APP_USERNAME / APP_PASSWORD.
"""

from __future__ import annotations

import os

from starlette.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.requests import Request

APP_USERNAME = os.environ.get("APP_USERNAME", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

_PUBLIC_PATHS = {"/login"}
_PUBLIC_PREFIXES = ("/assets/",)

_LOGIN_PAGE = """\
<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Đăng nhập — Nano Shark Content OS</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #16261c; color: #eee;
         display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
  form {{ background: #1f3226; padding: 32px; border-radius: 12px; width: 300px; }}
  h1 {{ font-size: 18px; margin: 0 0 20px; }}
  input {{ width: 100%; padding: 10px; margin: 6px 0 14px; border-radius: 6px; border: 1px solid #3a4d40;
           background: #12201a; color: #eee; box-sizing: border-box; }}
  button {{ width: 100%; padding: 10px; border-radius: 6px; border: none; background: #2f8f5e;
            color: white; font-weight: 600; cursor: pointer; }}
  .err {{ color: #ff8a8a; font-size: 13px; margin-bottom: 10px; }}
</style>
</head>
<body>
<form method="post" action="/login">
  <h1>Nano Shark Content OS</h1>
  {error}
  <label>Tài khoản</label>
  <input name="username" autofocus required>
  <label>Mật khẩu</label>
  <input name="password" type="password" required>
  <button type="submit">Đăng nhập</button>
</form>
</body>
</html>
"""


async def login_page(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse("/", status_code=302)
    return HTMLResponse(_LOGIN_PAGE.format(error=""))


async def login_submit(request: Request):
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")
    if not APP_PASSWORD:
        return HTMLResponse(
            _LOGIN_PAGE.format(
                error='<div class="err">Server chưa cấu hình APP_PASSWORD — liên hệ quản trị.</div>'
            ),
            status_code=500,
        )
    if username == APP_USERNAME and password == APP_PASSWORD:
        request.session["authenticated"] = True
        return RedirectResponse("/", status_code=302)
    return HTMLResponse(
        _LOGIN_PAGE.format(error='<div class="err">Sai tài khoản hoặc mật khẩu.</div>'),
        status_code=401,
    )


async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


class AuthMiddleware:
    """ASGI middleware: chặn mọi request chưa đăng nhập, trừ /login và /assets/*."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope["path"]
        if path in _PUBLIC_PATHS or path.startswith(_PUBLIC_PREFIXES):
            return await self.app(scope, receive, send)

        request = Request(scope, receive)
        if request.session.get("authenticated"):
            return await self.app(scope, receive, send)

        if path.startswith("/api/"):
            response = JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        else:
            response = RedirectResponse("/login", status_code=302)
        return await response(scope, receive, send)
