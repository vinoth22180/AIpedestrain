import json
import pickle
import os

report_path = r'data\vit_vellore\validation_report.json'
with open(report_path, 'r') as f:
    report = json.load(f)

print('--- ROUTING ---')
for k, route in report.get('routing_validation', {}).items():
    print(f'Route: {k}')
    print(f"  route_found: {route.get('route_found')}")
    if route.get('route_found'):
        print(f"  distance: {route.get('distance_m')}m")
        print(f"  entrance_nodes: {route.get('start_node')} -> {route.get('end_node')}")
        print(f"  stairs_used: {route.get('stairs_used')}")
        print(f"  accessible_route_available: {route.get('alternate_accessible_route_available')}")
    print()

print('--- TOPOLOGY ---')
top = report.get('topology', {})
print(f"connected_components: {top.get('connected_components')}")
print(f"edges: {top.get('edges')}")
print(f"nodes: {top.get('nodes')}")
print(f"entrance_nodes_total: {top.get('building_entrance_nodes')}")

graph_path = r'data\vit_vellore\processed\vit_vellore_academic_pedestrian_network.pkl'
import networkx as nx
if os.path.exists(graph_path):
    with open(graph_path, 'rb') as f:
        G = pickle.load(f)
    blocks_with_entrances = set()
    for n, d in G.nodes(data=True):
        if d.get('node_type') == 'building_entrance' and d.get('academic_block_id'):
            blocks_with_entrances.add(d['academic_block_id'])
    
    with open(r'data\vit_vellore\processed\academic_blocks.geojson', 'r') as f:
        ab_data = json.load(f)
    total_blocks = len(ab_data['features'])
    print(f"academic_blocks_total: {total_blocks}")
    print(f"blocks_without_entrance: {total_blocks - len(blocks_with_entrances)}")
