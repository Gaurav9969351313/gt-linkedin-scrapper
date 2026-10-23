import requests
import json
import time

flow_run_id = '984cc9c9-8179-4f19-9502-fa4d28c2a770'

for i in range(5):
    response = requests.post(
        'http://localhost:4200/api/task_runs/filter',
        headers={'Content-Type': 'application/json'},
        json={'flow_run_id': {'any_': [flow_run_id]}}
    )
    data = response.json()
    for t in data:
        if t.get('flow_run_id') == flow_run_id:
            print(f"[{time.strftime('%H:%M:%S')}] {t.get('name')}: {t.get('state_name')}")
    time.sleep(30)
