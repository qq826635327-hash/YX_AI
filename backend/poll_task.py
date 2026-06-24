"""轮询单个任务状态"""
import json
import urllib.request
import time
import sys

API_BASE = "http://127.0.0.1:8000/api"

def poll(task_id, max_wait=400):
    start = time.time()
    while time.time() - start < max_wait:
        url = f"{API_BASE}/tasks/{task_id}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        data = r.get("data", {})
        status = data.get("status", "unknown")
        progress = data.get("progress", 0)
        error = data.get("error_message", "")
        asset = data.get("output_asset_id", "")
        elapsed = int(time.time() - start)
        msg = f"[{elapsed}s] status={status} progress={progress}%"
        if error:
            msg += f" error={error[:150]}"
        if asset:
            msg += f" asset={asset}"
        print(msg)
        if status not in ("running", "pending"):
            break
        time.sleep(15)

if __name__ == "__main__":
    task_id = sys.argv[1] if len(sys.argv) > 1 else "f4f00d0e-437a-4a4a-9446-9910f03962f1"
    poll(task_id, max_wait=400)
