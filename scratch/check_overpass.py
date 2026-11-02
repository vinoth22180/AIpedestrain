import pandas as pd
import requests
import json

df = pd.read_csv(r'data\vit_vellore\raw\friend_base_pedestrian_network.csv')
nodes = list(set(df['from_node'].dropna().unique()).union(set(df['to_node'].dropna().unique())))
print(f'Total unique nodes to check: {len(nodes)}')

url = 'http://overpass-api.de/api/interpreter'

node_coords = {}
chunk_size = 300
for i in range(0, len(nodes), chunk_size):
    chunk = nodes[i:i+chunk_size]
    nodes_str = ','.join(map(str, map(int, chunk)))
    query = f'[out:json];node(id:{nodes_str});out;'
    
    r = requests.post(url, data={'data': query})
    if r.status_code == 200:
        data = r.json()
        for element in data.get('elements', []):
            node_coords[element['id']] = {'lat': element['lat'], 'lon': element['lon']}
        print(f'Chunk {i//chunk_size + 1}: Found {len(data.get("elements", []))} nodes.')
    else:
        print(f'Failed chunk {i//chunk_size + 1}')

print(f'Total nodes resolved: {len(node_coords)} out of {len(nodes)}')
