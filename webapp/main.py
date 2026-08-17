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

from webapp import persistent_storage  # noqa: E402

persistent_storage.bootstrap_persistent_data()

from webapp import ai_helper  # noqa: E402
from webapp import auth  # noqa: E402
from webapp import batch_production as bp  # noqa: E402
from webapp import daily_production as dp  # noqa: E402
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


# --- Daily Content Production ----------------------------------------------
# AI chỉ gọi khi có request tới đúng 3 route generate/score — không có job nền,
# không tự chạy. Lỗi AI (hết credit, sai key...) trả JSON lỗi rõ ràng, không
# crash server, không tạo dữ liệu giả.


async def api_daily_suggest(request):
    return JSONResponse(dp.suggest_topic())


async def api_daily_start(request):
    body = await request.json()
    pillar_num = body.get("pillar_num")
    topic_num = body.get("topic_num")
    if pillar_num is None or topic_num is None:
        suggestion = dp.suggest_topic()
        if "error" in suggestion:
            return JSONResponse({"ok": False, "error": suggestion["error"]}, status_code=400)
        pillar_num, topic_num = suggestion["pillar_num"], suggestion["topic_num"]
    try:
        record = dp.create_today_record(int(pillar_num), str(topic_num))
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "record": record})


async def api_daily_today(request):
    date = dp.today_str()
    record = dp.get_record(date)
    if record is None:
        return JSONResponse({"ok": True, "record": None, "detail": None})
    detail = dp.load_daily(date)
    return JSONResponse({"ok": True, "record": record, "detail": detail})


async def api_daily_detail(request):
    date = request.path_params["date"]
    record = dp.get_record(date)
    detail = dp.load_daily(date)
    if record is None:
        return JSONResponse({"ok": False, "error": f"Không có record ngày {date}"}, status_code=404)
    return JSONResponse({"ok": True, "record": record, "detail": detail})


async def api_daily_insight_sources(request):
    """Nguồn insight cho phép chọn tay — KHÔNG bịa, chỉ lấy từ data đã có."""
    return JSONResponse(
        {
            "priority_insights": dr.read_priority_insights(),
            "insight_bank": dr.read_insight_bank(),
            "voice_of_customer": dr.read_voice_of_customer(),
        }
    )


async def api_daily_set_insights(request):
    date = request.path_params["date"]
    body = await request.json()
    refs = body.get("insight_refs", [])
    try:
        record = dp.set_insights(date, refs)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "record": record})


async def api_daily_generate_ideas(request):
    date = request.path_params["date"]
    record = dp.get_record(date)
    if record is None:
        return JSONResponse({"ok": False, "error": f"Không có record ngày {date}"}, status_code=404)
    pillar_title = dr.pillar_title_by_num().get(record["pillar_num"], "")
    daily = dp.load_daily(date) or {}
    topic_title = next(
        (
            t.get("Chủ đề", "")
            for p in dr.read_content_pillars()
            if p["num"] == record["pillar_num"]
            for t in p["topics"]
            if str(t.get("#", "")).strip() == record["topic_num"]
        ),
        "",
    )
    try:
        ideas = ai_helper.generate_daily_ideas(
            pillar_title, topic_title, daily.get("insight_refs", [])
        )
    except Exception as exc:  # lỗi API (hết credit, sai key...) — trả lỗi rõ, không giả data
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    record = dp.set_ideas(date, ideas)
    return JSONResponse({"ok": True, "record": record, "ideas": ideas})


async def api_daily_generate_scripts(request):
    date = request.path_params["date"]
    daily = dp.load_daily(date)
    if not daily or not daily.get("ideas"):
        return JSONResponse(
            {"ok": False, "error": "Chưa có ý tưởng — tạo 10 ý tưởng trước."}, status_code=400
        )
    topic_title = next(
        (
            t.get("Chủ đề", "")
            for p in dr.read_content_pillars()
            if p["num"] == daily["pillar_num"]
            for t in p["topics"]
            if str(t.get("#", "")).strip() == daily["topic_num"]
        ),
        "",
    )
    try:
        raw_scripts = ai_helper.generate_daily_scripts(topic_title, daily["ideas"])
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    date_key = date.replace("-", "")
    scripts = []
    for i, s in enumerate(raw_scripts, start=1):
        s["script_id"] = f"d{date_key}_{i:02d}"
        # Cảnh báo pháp lý bắt buộc: gắn CỨNG ở backend, không phụ thuộc AI có
        # tuân thủ prompt hay không — đảm bảo 100% script luôn có câu này.
        s["mandatory_warning"] = ai_helper.MANDATORY_WARNING
        scripts.append(s)

    record = dp.set_scripts(date, scripts)
    return JSONResponse({"ok": True, "record": record, "scripts": scripts})


async def api_daily_score(request):
    date = request.path_params["date"]
    daily = dp.load_daily(date)
    if not daily or not daily.get("scripts"):
        return JSONResponse(
            {"ok": False, "error": "Chưa có script — tạo 10 script trước."}, status_code=400
        )
    try:
        scores = ai_helper.score_daily_scripts(daily["scripts"])
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    ranked = sorted(scores, key=lambda s: s.get("total", 0), reverse=True)
    top5 = [s["script_id"] for s in ranked[:5]]

    record = dp.set_scores(date, scores, top5)
    return JSONResponse({"ok": True, "record": record, "scores": scores, "top5": top5})


async def api_daily_select(request):
    date = request.path_params["date"]
    body = await request.json()
    script_id = body.get("script_id", "")
    try:
        record = dp.select_script(date, script_id)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "record": record})


async def api_daily_status(request):
    date = request.path_params["date"]
    body = await request.json()
    status = body.get("status", "")
    try:
        record = dp.set_status(date, status)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "record": record})


async def api_daily_history(request):
    days = int(request.query_params.get("days", 7))
    return JSONResponse(dp.get_history(days))


# --- Batch Content Production --------------------------------------------
# Song song với Daily Content Production — không đụng dp/content_calendar.json.
# "Quay 1 lần, đủ content cả tháng": 1 batch = N insight = N script, tất cả
# sống song song (không có khái niệm "chọn 1/N" như Daily Production).


async def api_batches_list(request):
    return JSONResponse(bp.list_batches())


async def api_batches_create(request):
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"ok": False, "error": "Cần nhập tên batch."}, status_code=400)
    record = bp.create_batch(name)
    return JSONResponse({"ok": True, "record": record})


async def api_batch_detail(request):
    batch_id = request.path_params["batch_id"]
    batch = bp.load_batch(batch_id)
    if batch is None:
        return JSONResponse({"ok": False, "error": f"Không có batch '{batch_id}'"}, status_code=404)
    return JSONResponse({"ok": True, "batch": batch})


async def api_batch_generate(request):
    """Sinh script cho 1 đợt insight (vd 10/lần) — nối thêm vào batch, không
    xoá script đã có. AI chỉ chạy khi route này được gọi (bấm nút), không nền."""
    batch_id = request.path_params["batch_id"]
    if bp.load_batch(batch_id) is None:
        return JSONResponse({"ok": False, "error": f"Không có batch '{batch_id}'"}, status_code=404)
    body = await request.json()
    insights = body.get("insights") or []
    if not insights:
        return JSONResponse({"ok": False, "error": "Cần ít nhất 1 insight."}, status_code=400)
    try:
        raw_scripts = ai_helper.generate_batch_scripts(insights)
    except Exception as exc:  # lỗi API (hết credit, sai key...) — trả lỗi rõ, không giả data
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    batch = bp.add_scripts(batch_id, insights, raw_scripts, ai_helper.MANDATORY_WARNING)
    return JSONResponse({"ok": True, "batch": batch})


async def api_batch_script_status(request):
    batch_id = request.path_params["batch_id"]
    script_id = request.path_params["script_id"]
    body = await request.json()
    status = body.get("status")  # None -> tự chuyển sang trạng thái kế tiếp
    try:
        batch = bp.set_script_status(batch_id, script_id, status)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "batch": batch})


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
        # --- Daily Content Production ---
        Route("/api/daily/suggest", api_daily_suggest),
        Route("/api/daily/start", api_daily_start, methods=["POST"]),
        Route("/api/daily/today", api_daily_today),
        Route("/api/daily/history", api_daily_history),
        Route("/api/daily/insight-sources", api_daily_insight_sources),
        Route("/api/daily/{date}", api_daily_detail),
        Route("/api/daily/{date}/insight", api_daily_set_insights, methods=["POST"]),
        Route("/api/daily/{date}/ideas", api_daily_generate_ideas, methods=["POST"]),
        Route("/api/daily/{date}/scripts", api_daily_generate_scripts, methods=["POST"]),
        Route("/api/daily/{date}/score", api_daily_score, methods=["POST"]),
        Route("/api/daily/{date}/select", api_daily_select, methods=["POST"]),
        Route("/api/daily/{date}/status", api_daily_status, methods=["POST"]),
        # --- Batch Content Production ---
        Route("/api/batches", api_batches_list),
        Route("/api/batches", api_batches_create, methods=["POST"]),
        Route("/api/batches/{batch_id}", api_batch_detail),
        Route("/api/batches/{batch_id}/generate", api_batch_generate, methods=["POST"]),
        Route("/api/batches/{batch_id}/scripts/{script_id}/status", api_batch_script_status, methods=["POST"]),
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
