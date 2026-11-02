import requests
import time
import os

# 1. Reset congestion
requests.post('http://127.0.0.1:8000/api/congestion/reset')

# 2. Get baseline route before video upload
base_res = requests.post(
    'http://127.0.0.1:8000/api/route',
    json={
        'origin': [79.15583638463455, 12.969035851408112],
        'destination': [79.16799249061337, 12.972225506107774],
        'profile': 'general'
    }
)
base_data = base_res.json()
print("=== 1. BASELINE ROUTE BEFORE VIDEO UPLOAD ===")
print("Baseline distance:", base_data['stats']['distance'])
print("Baseline edges count:", len(base_data['diagnostics']['baseline_edge_ids']))
print("Contains E000084?", 'E000084' in base_data['diagnostics']['selected_edge_ids'])

# 3. Upload video for location E001926
video_path = 'temp_videos/7b368389-7d10-4f64-9882-7d7c5d43e69b_12269404_2320_1080_30fps.mp4'
if not os.path.exists(video_path):
    print("Video file not found at", video_path)
    exit(1)

with open(video_path, 'rb') as f:
    upload_res = requests.post(
        'http://127.0.0.1:8000/api/congestion/video',
        data={'location': 'E001926'},
        files={'file': ('campus_walkway.mp4', f, 'video/mp4')}
    )

print("\n=== 2. VIDEO UPLOAD RESPONSE ===")
print("Status:", upload_res.status_code)
upload_json = upload_res.json()
print("Response:", upload_json)
job_id = upload_json.get('job_id')

# 4. Poll until completed
final_status = None
for i in range(45):
    time.sleep(1.5)
    s_res = requests.get(f'http://127.0.0.1:8000/api/congestion/status/{job_id}')
    status_data = s_res.json()
    st = status_data.get('status')
    if i % 3 == 0 or st in ['completed', 'failed']:
        print(f"Polling job {job_id}: status={st}, progress={status_data.get('progress')}")
    if st in ['completed', 'failed']:
        final_status = status_data
        break

print("\n=== 3. FINAL YOLO DETECTION RESULT ===")
print("Status:", final_status.get('status'))
print("Congestion Level:", final_status.get('congestion_level'))
print("Congestion Score:", final_status.get('congestion_score'))
print("Average People:", final_status.get('average_people'))
print("Peak People:", final_status.get('peak_people'))
print("Affected Edge IDs:", final_status.get('edge_ids'))

# 5. Query /api/route for MGR -> Gandhi Block now that YOLO processing has completed!
route_res = requests.post(
    'http://127.0.0.1:8000/api/route',
    json={
        'origin': [79.15583638463455, 12.969035851408112],
        'destination': [79.16799249061337, 12.972225506107774],
        'profile': 'general'
    }
)
r_data = route_res.json()
print("\n=== 4. LIVE ROUTE AFTER VIDEO PROCESSED ===")
print("HTTP Status:", route_res.status_code)
print("Distance:", r_data['stats']['distance'], f"(vs Baseline: {base_data['stats']['distance']})")
print("Explanation:", r_data['route_explanation']['reason'])
print("Avoids congestion flag:", r_data['route_explanation']['avoids_congestion'])
diag = r_data.get('diagnostics', {})
print("Rerouted flag:", diag.get('rerouted'))
print("Baseline HIGH edges:", diag.get('baseline_high_edges'))
print("Selected HIGH edges:", diag.get('selected_high_edges'))
print("Contains E000084?", 'E000084' in diag.get('selected_edge_ids', []))
print("Contains E000083?", 'E000083' in diag.get('selected_edge_ids', []))
print("Contains E001926?", 'E001926' in diag.get('selected_edge_ids', []))

assert 'E000084' not in diag.get('selected_edge_ids', []), "Selected route still contains E000084!"
assert 'E000083' not in diag.get('selected_edge_ids', []), "Selected route still contains E000083!"
assert r_data['route_explanation']['avoids_congestion'] is True, "Expected avoids_congestion=True!"
assert diag.get('rerouted') is True, "Expected diagnostics.rerouted=True!"

print("\n>>> LIVE SERVER DYNAMIC REROUTING VERIFIED 100% END-TO-END! <<<")
