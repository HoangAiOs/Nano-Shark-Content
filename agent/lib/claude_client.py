"""Wrapper mỏng quanh Claude Agent SDK để các phase dùng chung.

Mỗi phase chỉ cần gọi `run_agent_task(...)` với một prompt mô tả rõ việc cần làm
(bao gồm đường dẫn file cần đọc/ghi) và danh sách tool cần bật. Agent sẽ tự
đọc/ghi file bằng tool Read/Write có sẵn của Claude Agent SDK, không cần code
tự parse output của model.
"""

from __future__ import annotations

import asyncio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from agent.config import MODEL, PROJECT_ROOT

# Lỗi tạm thời (mạng chập chờn, server quá tải...) — đáng để tự động thử lại.
# Lỗi hết credit / sai API key thì thử lại vô ích, cần con người xử lý trước.
_TRANSIENT_ERROR_MARKERS = (
    "connection closed",
    "connection reset",
    "connection error",
    "timed out",
    "timeout",
    "overloaded",
    "529",
    "502",
    "503",
    "internal server error",
)


async def _run_once(
    prompt: str,
    *,
    allowed_tools: list[str],
    system_prompt: str,
    max_turns: int,
) -> tuple[str, Exception | None]:
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        permission_mode="acceptEdits",
        model=MODEL,
        cwd=str(PROJECT_ROOT),
        max_turns=max_turns,
    )

    final_text_parts: list[str] = []

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
                        final_text_parts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        print(f"  [dùng tool: {block.name}]")
            elif isinstance(message, ResultMessage):
                print(f"--- Hoàn tất (lý do dừng: {message.terminal_reason}) ---")
    except Exception as exc:  # claude_agent_sdk raises a plain Exception for API-level errors
        return "\n".join(final_text_parts), exc

    return "\n".join(final_text_parts), None


def _print_error_hint(error_text: str) -> None:
    lowered = error_text.lower()
    print(f"\n❌ Agent dừng giữa chừng do lỗi: {error_text}")
    if "credit" in lowered or "balance" in lowered:
        print(
            "   → Tài khoản Anthropic đang hết credit. Nạp thêm tại "
            "https://platform.claude.com/settings/billing rồi chạy lại lệnh này."
        )
    elif "429" in lowered or "rate limit" in lowered:
        print("   → Đang bị giới hạn tốc độ gọi API (rate limit). Đợi một lúc rồi thử lại.")
    elif "401" in lowered or "authentication" in lowered or "api key" in lowered or "api_key" in lowered:
        print("   → API key có thể sai hoặc đã bị thu hồi. Kiểm tra lại ANTHROPIC_API_KEY trong file .env.")


async def _run(
    prompt: str,
    *,
    allowed_tools: list[str],
    system_prompt: str,
    max_turns: int,
    max_retries: int = 2,
) -> str:
    attempt = 0
    while True:
        attempt += 1
        text, error = await _run_once(
            prompt, allowed_tools=allowed_tools, system_prompt=system_prompt, max_turns=max_turns
        )
        if error is None:
            return text

        error_text = str(error)
        is_transient = any(marker in error_text.lower() for marker in _TRANSIENT_ERROR_MARKERS)

        if is_transient and attempt <= max_retries:
            wait_seconds = 5 * attempt
            print(
                f"\n⚠️  Lỗi tạm thời (lần {attempt}/{max_retries}): {error_text}\n"
                f"   Tự động thử lại sau {wait_seconds}s..."
            )
            await asyncio.sleep(wait_seconds)
            continue

        _print_error_hint(error_text)
        return text


def run_agent_task(
    prompt: str,
    *,
    allowed_tools: list[str],
    system_prompt: str,
    max_turns: int = 40,
) -> str:
    """Chạy một tác vụ agent đồng bộ (bọc async cho tiện dùng từ CLI).

    Tự động thử lại tối đa 2 lần nếu gặp lỗi tạm thời (mất kết nối, server quá
    tải...). Lỗi hết credit / sai API key sẽ không thử lại — in hướng dẫn xử lý
    rồi dừng, vì thử lại cũng sẽ thất bại y hệt.
    """
    return asyncio.run(
        _run(prompt, allowed_tools=allowed_tools, system_prompt=system_prompt, max_turns=max_turns)
    )
