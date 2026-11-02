from src.graph_manager import load_or_build_graph
from src.darr.router import compute_darr_routes

G = load_or_build_graph()
origin = (79.155836, 12.969035) # MGR
destination = (79.159534, 12.970823) # TT

res = compute_darr_routes(G, origin, destination, 'general')
print('Status:', res['status'])
print('Candidate count:', len(res['candidate_routes']))
for c in res['candidate_routes']:
    print(f"Candidate {c['route_id']}: {c['name']} | Dist: {c['total_distance']}m | Time: {c['estimated_travel_time']}s | Status: {c['selection_status']} | Score: {c['final_route_score']} | MAL: {c['marginal_accessibility_loss']}")
print('Selected explanation:', res['decision_summary'])
print('Network resilience:', res['network_resilience'])
print('Collapse risk:', res['collapse_risk']['collapse_risk'])
