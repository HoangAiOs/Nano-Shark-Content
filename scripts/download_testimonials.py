"""Tải folder Google Drive (video testimonial) với tự động retry khi mất kết nối."""

import time

import gdown

FOLDER_ID = "1EkVSWONcyRf3NYObUq1xyLO2wnrN4vwx"
URL = f"https://drive.google.com/drive/folders/{FOLDER_ID}"
MAX_RETRIES = 8

for attempt in range(1, MAX_RETRIES + 1):
    try:
        print(f"\n=== Lần thử {attempt}/{MAX_RETRIES} ===", flush=True)
        result = gdown.download_folder(
            url=URL, output="data/raw_videos", quiet=False, use_cookies=False, resume=True
        )
        print(f"DONE {len(result) if result else 0} files", flush=True)
        for r in result or []:
            print(r, flush=True)
        break
    except Exception as exc:
        print(f"LỖI lần thử {attempt}: {exc}", flush=True)
        if attempt == MAX_RETRIES:
            print("Hết số lần thử, dừng lại.", flush=True)
            raise
        time.sleep(10)
