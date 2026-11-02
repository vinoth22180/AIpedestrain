import urllib.request
import json

landmarks_req = urllib.request.urlopen('http://localhost:8000/api/landmarks')
landmarks = json.loads(landmarks_req.read().decode())
print(f"Live Landmarks loaded: {len(landmarks)}")

mgr = next(l for l in landmarks if l['name'] == 'MGR')
tt = next(l for l in landmarks if l['name'] == 'TT')

print("\n--- LIVE ROUTING OVER HTTP ---")
for prof in ['elderly', 'general', 'pregnant', 'wheelchair']:
    req_data = json.dumps({
        'origin': mgr['coords'],
        'destination': tt['coords'],
        'profile': prof
    }).encode('utf-8')
    req = urllib.request.Request('http://localhost:8000/api/route', data=req_data, headers={'Content-Type': 'application/json'})
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode())
    dist = data['stats']['distance']
    cost = data['stats']['cost']
    decision = data['decision_summary']
    candidates_count = len(data.get('candidate_routes', []))
    print(f"Profile: {prof:10s} | HTTP {res.status} | Dist: {dist:.1f}m | Cost: {cost:.1f} | Candidates: {candidates_count}")
    print(f"   Decision summary: {decision}")
