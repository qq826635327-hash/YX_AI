import urllib.request, json, time

task_ids = [
    ('2K Image', '0a53a6fe-c78b-4d90-8a32-bba1ce91c634'),
    ('4K Image', '13406844-b724-4a97-a164-8f7bf51a4157'),
    ('2K Video', '555b1207-1bed-4eab-80cf-e5a15307a365'),
]

for label, tid in task_ids:
    try:
        resp = urllib.request.urlopen(f'http://127.0.0.1:8000/api/tasks/{tid}', timeout=10)
        d = json.loads(resp.read().decode())['data']
        err = (d.get('error_message') or '')[:200]
        asset = d.get('output_asset_id') or ''
        print(f'{label}: status={d["status"]} progress={d["progress"]} asset={asset} err={err}')
    except Exception as e:
        print(f'{label}: error={e}')
