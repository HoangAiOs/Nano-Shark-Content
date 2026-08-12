"""Dashboard web cho pipeline agent — đọc dữ liệu thật từ data/.

2 tính năng (Não Marketing, Kiến tạo 1.000 video) có gọi Claude API thật (qua
webapp/ai_helper.py, model Haiku giá rẻ) để sinh ý tưởng — mọi tính năng khác
chỉ đọc/ghi file local, không gọi AI.

Chạy: python -m webapp.main   (từ thư mục gốc project, venv đã activate)
Mặc định mở tại http://127.0.0.1:8811
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from starlette.applications import Starlette  # noqa: E402
from starlette.middleware import Middleware  # noqa: E402
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402
from starlette.responses import FileResponse, JSONResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

from webapp import ai_helper  # noqa: E402
from webapp import auth  # noqa: E402
from webapp import data_reader as dr  # noqa: E402

SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
if not os.environ.get("SESSION_SECRET"):
    print(
        "⚠️  SESSION_SECRET chưa được set trong .env — dùng key ngẫu nhiên tạm thời "
        "(sẽ đăng xuất hết mọi người mỗi lần restart server). Đặt SESSION_SECRET cố định "
        "trong .env trước khi deploy thật."
    )

STATIC_DIR = Path(__file__).resolve().parent / "static"


async def api_overview(request):
    return JSONResponse(dr.read_overview())


async def api_research(request):
    return JSONResponse(dr.read_research_summary())


async def api_voice_of_customer(request):
    return JSONResponse(dr.read_voice_of_customer())


async def api_insight_bank(request):
    return JSONResponse(dr.read_insight_bank())


async def api_content_pillars(request):
    return JSONResponse(dr.read_content_pillars())


async def api_content_wave1(request):
    return JSONResponse(dr.read_content_wave1())


async def api_insights(request):
    return JSONResponse(dr.read_priority_insights())


async def api_insight_status(request):
    num = request.path_params["num"]
    body = await request.json()
    status = body.get("status", "Mới")
    dr.set_insight_triage(num, status)
    return JSONResponse({"ok": True, "num": num, "status": status})


async def api_ideas_today(request):
    return JSONResponse(dr.read_ideas_today())


async def api_toggle_quay(request):
    script_id = request.path_params["script_id"]
    new_status = dr.toggle_quay(script_id)
    return JSONResponse({"ok": True, "script_id": script_id, "quay_xong": new_status})


async def api_script_detail(request):
    script_id = request.path_params["script_id"]
    content = dr.read_script_detail(script_id)
    return JSONResponse({"script_id": script_id, "content": content})


async def api_portfolio(request):
    return JSONResponse(dr.read_portfolio())


# --- 1. Não Marketing ---------------------------------------------------


async def api_goal_get(request):
    return JSONResponse({"goal": dr.get_goal(), "ideas": dr.get_goal_ideas()})


async def api_goal_save(request):
    body = await request.json()
    dr.set_goal(body.get("goal", ""))
    return JSONResponse({"ok": True})


async def api_objective_engine(request):
    goal = dr.get_goal()
    insight_texts = [i["insight"] for i in dr.read_priority_insights()]
    try:
        ideas = ai_helper.generate_ideas_from_goal(goal, insight_texts)
    except Exception as exc:  # lỗi API (hết credit, sai key...) — trả về rõ ràng thay vì crash
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    dr.set_goal_ideas(ideas)
    return JSONResponse({"ok": True, "ideas": ideas})


# --- 3. Belief Map --------------------------------------------------------


async def api_belief_map(request):
    return JSONResponse(dr.read_belief_map())


# --- 6. Kiến tạo 1.000 video ----------------------------------------------


async def api_expand_angles(request):
    num = request.path_params["num"]
    cached = dr.get_cached_angles(num)
    if cached:
        return JSONResponse({"ok": True, "angles": cached, "cached": True})
    insight = next((i for i in dr.read_priority_insights() if i["num"] == num), None)
    if not insight:
        return JSONResponse({"ok": False, "error": "insight not found"}, status_code=404)
    try:
        angles = ai_helper.expand_insight_angles(insight["insight"])
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    dr.set_cached_angles(num, angles)
    return JSONResponse({"ok": True, "angles": angles, "cached": False})


# --- 7. Bản đồ nội dung ----------------------------------------------------


async def api_content_map(request):
    return JSONResponse(dr.read_content_map())


# --- 10-11. Upload video + Hàng đợi ----------------------------------------


async def api_video_upload(request):
    form = await request.form()
    upload = form.get("file")
    if upload is None:
        return JSONResponse({"ok": False, "error": "no file"}, status_code=400)
    dr.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    dest = dr.UPLOADS_DIR / upload.filename
    contents = await upload.read()
    dest.write_bytes(contents)
    return JSONResponse({"ok": True, "filename": upload.filename})


async def api_video_queue(request):
    return JSONResponse(dr.list_video_queue())


async def api_toggle_publish(request):
    filename = request.path_params["filename"]
    platform = request.path_params["platform"]
    new_status = dr.toggle_publish_status(filename, platform)
    return JSONResponse({"ok": True, "status": new_status})


# --- 12. Ads Autopilot (báo cáo, không tự bật/tắt chi tiêu thật) ----------


async def api_ads_autopilot(request):
    return JSONResponse(dr.read_ads_autopilot())


async def index(request):
    # no-store: index.html thay đổi khá thường xuyên trong lúc phát triển dashboard —
    # tránh trình duyệt lỡ giữ bản cache cũ khi bấm quay lại/mở lại tab.
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


app = Starlette(
    middleware=[
        Middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax"),
        Middleware(auth.AuthMiddleware),
    ],
    routes=[
        Route("/login", auth.login_page, methods=["GET"]),
        Route("/login", auth.login_submit, methods=["POST"]),
        Route("/logout", auth.logout, methods=["GET"]),
        Route("/", index),
        Route("/api/overview", api_overview),
        Route("/api/research", api_research),
        Route("/api/voice-of-customer", api_voice_of_customer),
        Route("/api/insight-bank", api_insight_bank),
        Route("/api/content-pillars", api_content_pillars),
        Route("/api/content-wave1", api_content_wave1),
        Route("/api/insights", api_insights),
        Route("/api/insights/{num}/status", api_insight_status, methods=["POST"]),
        Route("/api/ideas-today", api_ideas_today),
        Route("/api/ideas-today/{script_id}/toggle-quay", api_toggle_quay, methods=["POST"]),
        Route("/api/scripts/{script_id}", api_script_detail),
        Route("/api/portfolio", api_portfolio),
        Route("/api/goal", api_goal_get),
        Route("/api/goal", api_goal_save, methods=["POST"]),
        Route("/api/objective-engine", api_objective_engine, methods=["POST"]),
        Route("/api/belief-map", api_belief_map),
        Route("/api/content-map", api_content_map),
        Route("/api/insights/{num}/expand-angles", api_expand_angles, methods=["POST"]),
        Route("/api/video-upload", api_video_upload, methods=["POST"]),
        Route("/api/video-queue", api_video_queue),
        Route("/api/video-queue/{filename}/{platform}/toggle", api_toggle_publish, methods=["POST"]),
        Route("/api/ads-autopilot", api_ads_autopilot),
    ],
)

app.mount("/assets", StaticFiles(directory=str(STATIC_DIR)), name="assets")


if __name__ == "__main__":
    import uvicorn

    # PORT do hosting (Render...) cấp qua biến môi trường; mặc định 8811 khi chạy local.
    # host 0.0.0.0 để hosting cloud định tuyến được vào container — vẫn truy cập bình
    # thường qua 127.0.0.1:8811 khi chạy trên máy local.
    port = int(os.environ.get("PORT", 8811))
    uvicorn.run("webapp.main:app", host="0.0.0.0", port=port, reload=False)
