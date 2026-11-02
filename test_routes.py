import requests

landmarks = requests.get('http://127.0.0.1:8000/api/academic_blocks').json()['features']
locs = {f['properties'].get('short_name') or f['properties'].get('name'): f['geometry']['coordinates'] for f in landmarks}

for origin in ['MGR', 'TT', 'PRP', 'SMV']:
    if origin in locs and 'SJT' in locs:
        payload = {'origin': locs[origin], 'destination': locs['SJT'], 'profile': 'general'}
        resp = requests.post('http://127.0.0.1:8000/api/route', json=payload)
        data = resp.json()
        print(f'{origin} -> SJT: dist={data.get("stats", {}).get("distance")}, cost={data.get("stats", {}).get("cost")}, penalty={data.get("congestion_score")}')
