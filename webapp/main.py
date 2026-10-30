"""Dashboard web cho pipeline agent — đọc dữ liệu thật từ data/.

Toàn bộ nội dung/ý tưởng hiển thị đều lấy từ file tĩnh đã có sẵn trong data/
(kịch bản, Content Pillars, Insight Bank, Voice of Customer...) — dashboard
KHÔNG gọi AI trong lúc chạy. Nếu cần sinh nội dung mới, dùng lại pipeline CLI
`python -m agent.cli ...` (agent/phases/*.py), rồi dashboard sẽ đọc kết quả.

Chạy: python -m webapp.main   (từ thư mục gốc project, venv đã activate)
Mặc định mở tại http://127.0.0.1:8811
"""

from __future__ import annotations

import asyncio
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

from webapp import auth  # noqa: E402
from webapp import data_reader as dr  # noqa: E402
from webapp import inbox_store  # noqa: E402
from webapp import script_generator  # noqa: E402

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


async def api_original_scripts(request):
    return JSONResponse(dr.read_original_scripts())


async def api_original_script_detail(request):
    script_id = request.path_params["script_id"]
    return JSONResponse(dr.read_original_script_detail(script_id))


async def api_toggle_original_quay(request):
    script_id = request.path_params["script_id"]
    new_status = dr.toggle_original_quay(script_id)
    if new_status is None:
        return JSONResponse({"ok": False, "error": "Không có kịch bản gốc này"}, status_code=404)
    return JSONResponse({"ok": True, "script_id": script_id, "quay_xong": new_status})


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
    return JSONResponse({"goal": dr.get_goal()})


async def api_goal_save(request):
    body = await request.json()
    dr.set_goal(body.get("goal", ""))
    return JSONResponse({"ok": True})


# --- 3. Belief Map --------------------------------------------------------


async def api_belief_map(request):
    return JSONResponse(dr.read_belief_map())


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

# --- Insight từ Inbox (tin nhắn khách thật — chỉ sau đăng nhập, không cache) ---

_NO_STORE = {"Cache-Control": "no-store"}


def _inbox_json(data, status_code=200):
    return JSONResponse(data, status_code=status_code, headers=_NO_STORE)


async def api_inbox_list(request):
    data = inbox_store.list_insights()
    data["library_scripts"] = {r["script_id"]: r["name"] for r in dr.read_ideas_today()}
    data["has_api_key"] = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return _inbox_json(data)


async def api_inbox_add(request):
    body = await request.json()
    entries = body.get("items") if isinstance(body, dict) else None
    try:
        added = inbox_store.add_insights(entries or [])
    except inbox_store.InboxError as e:
        return _inbox_json({"ok": False, "error": str(e)}, 400)
    return _inbox_json({"ok": True, "added": added})


async def api_inbox_update(request):
    insight_id = request.path_params["insight_id"]
    try:
        rec = inbox_store.update_insight(insight_id, await request.json())
    except inbox_store.InboxError as e:
        return _inbox_json({"ok": False, "error": str(e)}, 400)
    except KeyError:
        return _inbox_json({"ok": False, "error": "Không có insight này"}, 404)
    return _inbox_json({"ok": True, "item": rec})


async def api_inbox_delete(request):
    try:
        inbox_store.delete_insight(request.path_params["insight_id"])
    except KeyError:
        return _inbox_json({"ok": False, "error": "Không có insight này"}, 404)
    return _inbox_json({"ok": True})


_generation_tasks: set = set()


async def _run_generation(insight_id: str, rec: dict, script_no: str) -> None:
    try:
        result = await script_generator.generate(rec, script_no)
        inbox_store.finish_generation(insight_id, result)
    except script_generator.GeneratorError as e:
        inbox_store.fail_generation(insight_id, str(e))
    except Exception as e:  # noqa: BLE001 — mọi lỗi khác cũng phải ghi lại, không để kẹt "đang sinh"
        inbox_store.fail_generation(insight_id, f"Lỗi không mong đợi: {e}")


async def api_inbox_generate(request):
    """Sinh kịch bản bằng Claude API — chạy nền (30–120 giây), trình duyệt hỏi lại trạng thái qua /api/inbox."""
    insight_id = request.path_params["insight_id"]
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _inbox_json({"ok": False, "error": script_generator.NO_KEY_MESSAGE, "no_key": True}, 503)
    library_ids = {r["script_id"] for r in dr.read_ideas_today(include_inbox=False)}
    try:
        rec, script_no = inbox_store.start_generation(insight_id, library_ids)
    except PermissionError as e:
        return _inbox_json({"ok": False, "error": str(e)}, 403)
    except inbox_store.InboxError as e:
        return _inbox_json({"ok": False, "error": str(e)}, 409)
    except KeyError:
        return _inbox_json({"ok": False, "error": "Không có insight này"}, 404)
    task = asyncio.create_task(_run_generation(insight_id, rec, script_no))
    _generation_tasks.add(task)
    task.add_done_callback(_generation_tasks.discard)
    return _inbox_json({"ok": True, "script_no": script_no}, 202)


async def api_inbox_script(request):
    insight_id = request.path_params["insight_id"]
    try:
        if request.method == "POST":
            body = await request.json()
            markdown = body.get("markdown") or ""
            rec = next(r for r in inbox_store.list_insights()["items"] if r["id"] == insight_id)
            check = script_generator.check_script(markdown, rec)
            rec = inbox_store.save_manual_edit(insight_id, markdown, check)
            return _inbox_json({"ok": True, "item": rec})
        return _inbox_json({"ok": True, "markdown": inbox_store.read_generated(insight_id)})
    except (KeyError, StopIteration):
        return _inbox_json({"ok": False, "error": "Không có insight này"}, 404)
    except inbox_store.InboxError as e:
        return _inbox_json({"ok": False, "error": str(e)}, 400)


async def api_inbox_evidence_upload(request):
    form = await request.form()
    upload = form.get("file")
    if upload is None:
        return _inbox_json({"ok": False, "error": "Chưa chọn ảnh"}, 400)
    try:
        rec = inbox_store.save_evidence(request.path_params["insight_id"], upload.filename, await upload.read())
    except inbox_store.InboxError as e:
        return _inbox_json({"ok": False, "error": str(e)}, 400)
    except KeyError:
        return _inbox_json({"ok": False, "error": "Không có insight này"}, 404)
    return _inbox_json({"ok": True, "item": rec})


async def api_inbox_evidence_file(request):
    path = inbox_store.evidence_path(request.path_params["name"])
    if path is None:
        return _inbox_json({"ok": False, "error": "Không có ảnh này"}, 404)
    return FileResponse(path, headers={"Cache-Control": "private, no-store"})


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
        Route("/api/original-scripts", api_original_scripts),
        Route("/api/original-scripts/{script_id}", api_original_script_detail),
        Route("/api/original-scripts/{script_id}/toggle-quay", api_toggle_original_quay, methods=["POST"]),
        Route("/api/voice-of-customer", api_voice_of_customer),
        Route("/api/inbox", api_inbox_list),
        Route("/api/inbox", api_inbox_add, methods=["POST"]),
        Route("/api/inbox/evidence/{name}", api_inbox_evidence_file),
        Route("/api/inbox/{insight_id}", api_inbox_update, methods=["POST"]),
        Route("/api/inbox/{insight_id}/delete", api_inbox_delete, methods=["POST"]),
        Route("/api/inbox/{insight_id}/generate", api_inbox_generate, methods=["POST"]),
        Route("/api/inbox/{insight_id}/script", api_inbox_script, methods=["GET", "POST"]),
        Route("/api/inbox/{insight_id}/evidence", api_inbox_evidence_upload, methods=["POST"]),
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
        Route("/api/belief-map", api_belief_map),
        Route("/api/content-map", api_content_map),
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
