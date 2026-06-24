import urllib.request, json, time

# 等待新任务出现
print("等待新任务提交...")
last_ids = set()
r = urllib.request.urlopen("http://127.0.0.1:8000/api/tasks?page_size=5")
d = json.loads(r.read())
for t in d.get("data", {}).get("items", []):
    last_ids.add(t["id"])

task_id = None
for i in range(40):
    time.sleep(3)
    r = urllib.request.urlopen("http://127.0.0.1:8000/api/tasks?page_size=5")
    d = json.loads(r.read())
    items = d.get("data", {}).get("items", [])
    for t in items:
        if t["id"] not in last_ids:
            task_id = t["id"]
            break
    if task_id:
        break
    # 也检查是否有 running 的
    active = [t for t in items if t["status"] in ("running", "pending", "queued")]
    if active:
        task_id = active[0]["id"]
        break

if not task_id:
    print("等待超时，没有新任务")
    exit()

print(f"\n=== 监控任务 {task_id[:8]} ===")
for i in range(80):
    r = urllib.request.urlopen(f"http://127.0.0.1:8000/api/tasks/{task_id}")
    d = json.loads(r.read())
    t = d.get("data", {})
    status = t["status"]
    progress = t["progress"]
    error = (t.get("error_message") or "")[:200]
    print(f"  [{i+1}] status={status} progress={progress} error={error}")
    if status in ("succeeded", "failed", "cancelled"):
        op = t.get("output_payload") or {}
        if op:
            print(f"  output_payload: {json.dumps(op, ensure_ascii=False)[:500]}")
        break
    time.sleep(3)
